from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, desc, asc
from sqlalchemy.exc import IntegrityError
from .database import Base, engine, get_db, SessionLocal
from .models import *
from .security import current_user, hash_password, verify_password, create_token
from .config import settings
from .seed import seed, policies
from pathlib import Path
from difflib import SequenceMatcher
import json, re, time
app=FastAPI(title="ShopSmart AI API", version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
Base.metadata.create_all(bind=engine)
with SessionLocal() as db: seed(db)
class Register(BaseModel): name:str; email:EmailStr; password:str
class Login(BaseModel): email:EmailStr; password:str
class CartUpdate(BaseModel): product_id:str; quantity:int=1
class Ask(BaseModel): message:str

def product_out(p): return {"id":p.id,"name":p.name,"category":p.category.name if p.category else "General","brand":p.brand,"description":p.description,"price":p.price,"rating":p.rating,"stock":p.stock,"image_url":p.image_url,"specs":p.specs}
def order_out(o): return {"id":o.id,"total":o.total,"status":o.status,"delivery_type":o.delivery_type,"created_at":o.created_at.isoformat(),"items":[{"product":product_out(i.product),"quantity":i.quantity,"price":i.price} for i in o.items],"events":[{"status":e.status,"timestamp":e.timestamp.isoformat()} for e in o.events]}
def llm():
    if not settings.groq_api_key:return None
    try:
        from langchain_groq import ChatGroq
        return ChatGroq(model=settings.groq_model,api_key=settings.groq_api_key,temperature=0.2,max_retries=2)
    except Exception:return None
def ai_log(db,user_id,endpoint,q,response,sources=None,start=None):
    db.add(AILog(user_id=user_id,endpoint=endpoint,query=q,response_json=response,sources_json=sources or [],latency_ms=int((time.time()-(start or time.time()))*1000))); db.commit()
@app.get("/api/health")
def health(): return {"status":"ok","llm_provider":settings.llm_provider,"groq_configured":bool(settings.groq_api_key)}
@app.post("/api/auth/register")
def register(payload:Register,db:Session=Depends(get_db)):
    if len(payload.password)<8: raise HTTPException(400,"Password must be at least 8 characters")
    u=User(name=payload.name,email=payload.email,password_hash=hash_password(payload.password)); db.add(u)
    try: db.commit(); db.refresh(u)
    except IntegrityError: db.rollback(); raise HTTPException(409,"Email already registered")
    return {"access_token":create_token(u),"token_type":"bearer","user":{"id":u.id,"name":u.name,"email":u.email,"membership_tier":u.membership_tier}}
@app.post("/api/auth/login")
def login(p:Login,db:Session=Depends(get_db)):
    u=db.query(User).filter_by(email=p.email).first()
    if not u or not verify_password(p.password,u.password_hash): raise HTTPException(401,"Email or password is incorrect")
    return {"access_token":create_token(u),"token_type":"bearer","user":{"id":u.id,"name":u.name,"email":u.email,"membership_tier":u.membership_tier}}
@app.get("/api/auth/me")
def me(u:User=Depends(current_user)): return {"id":u.id,"name":u.name,"email":u.email,"membership_tier":u.membership_tier}
@app.get("/api/categories")
def categories(db:Session=Depends(get_db)): return [{"id":c.id,"name":c.name} for c in db.query(Category).order_by(Category.name).all()]
BASIC_SEARCH_STOP_WORDS={"a","an","and","are","for","from","in","is","it","of","on","or","the","to","with","this","that","me","find","show","search","product","products"}
def basic_search_score(product,terms):
    specs=product.specs or {}
    type_text=str(specs.get("type", ""))
    details=str(specs.get("details", ""))
    fields={
        "name":(product.name or "").lower(),
        "brand":(product.brand or "").lower(),
        "description":(product.description or "").lower(),
        "specs":(type_text+" "+details).lower(),
    }
    all_text=" ".join(fields.values())
    words=set(re.findall(r"[a-z0-9]+",all_text))
    score=0.0
    matched=0
    for term in terms:
        if term in words:
            matched+=1
            score+=1.0
            if term in fields["name"]: score+=2.5
            elif term in type_text.lower(): score+=2.0
            elif term in fields["brand"]: score+=1.5
            elif term in fields["description"]: score+=1.0
            else: score+=0.8
            continue
        if len(term)<4: continue
        if any(term in word or word in term for word in words if min(len(term),len(word))>=4):
            matched+=1
            score+=0.55
            continue
        similarity=max((SequenceMatcher(None,term,word).ratio() for word in words if min(len(term),len(word))>=4),default=0.0)
        if similarity>=0.76:
            matched+=1
            score+=similarity*0.65
    if not matched:return 0.0
    # Reward results that match a larger share of the useful query terms.
    return score+(matched/len(terms))*1.5

@app.get("/api/products")
def products(q:str="",category:str="",brand:str="",min_price:float|None=None,max_price:float|None=None,min_rating:float=0,sort:str="featured",page:int=1,limit:int=12,db:Session=Depends(get_db)):
    query=db.query(Product).options(joinedload(Product.category))
    if category: query=query.join(Category).filter(Category.name==category)
    if brand: query=query.filter(Product.brand==brand)
    if min_price is not None: query=query.filter(Product.price>=min_price)
    if max_price is not None: query=query.filter(Product.price<=max_price)
    query=query.filter(Product.rating>=min_rating)
    sortmap={"price_asc":asc(Product.price),"price_desc":desc(Product.price),"rating":desc(Product.rating),"name":asc(Product.name),"featured":desc(Product.rating)}
    page=max(1,page); limit=min(max(1,limit),100)
    if q.strip():
        terms=[term for term in re.findall(r"[a-z0-9]+",q.lower()) if term not in BASIC_SEARCH_STOP_WORDS]
        candidates=query.all()
        ranked=[(basic_search_score(product,terms),product) for product in candidates] if terms else [(1.0,product) for product in candidates]
        ranked=[entry for entry in ranked if entry[0]>0]
        tie_breakers={"price_asc":lambda p:p.price,"price_desc":lambda p:-p.price,"rating":lambda p:-p.rating,"name":lambda p:p.name.lower(),"featured":lambda p:-p.rating}
        ranked.sort(key=lambda entry:(-entry[0],tie_breakers.get(sort,lambda p:-p.rating)(entry[1])))
        total=len(ranked)
        rows=[product for _,product in ranked[(page-1)*limit:page*limit]]
    else:
        total=query.count()
        rows=query.order_by(sortmap.get(sort,desc(Product.rating))).offset((page-1)*limit).limit(limit).all()
    return {"items":[product_out(p) for p in rows],"total":total,"page":page,"pages":(total+limit-1)//limit}
@app.get("/api/products/{product_id}")
def product_detail(product_id:str,db:Session=Depends(get_db)):
    p=db.query(Product).options(joinedload(Product.category)).filter_by(id=product_id).first()
    if not p: raise HTTPException(404,"Product not found")
    return product_out(p)
@app.get("/api/cart")
def get_cart(db:Session=Depends(get_db),u:User=Depends(current_user)):
    rows=db.query(CartItem).filter_by(user_id=u.id).all(); items=[]
    for i in rows:
        p=db.query(Product).options(joinedload(Product.category)).get(i.product_id)
        if p: items.append({"product":product_out(p),"quantity":i.quantity})
    return {"items":items,"total":sum(x["product"]["price"]*x["quantity"] for x in items)}
@app.post("/api/cart")
def cart_add(body:CartUpdate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if body.quantity<1: raise HTTPException(400,"Quantity must be positive")
    p=db.get(Product,body.product_id)
    if not p: raise HTTPException(404,"Product not found")
    item=db.query(CartItem).filter_by(user_id=u.id,product_id=p.id).first()
    qty=(item.quantity if item else 0)+body.quantity
    if p.stock<qty: raise HTTPException(409,"Requested quantity is not available")
    if item:item.quantity=qty
    else:db.add(CartItem(user_id=u.id,product_id=p.id,quantity=qty))
    db.commit(); return {"message":"Cart updated"}
@app.patch("/api/cart/{product_id}")
def cart_update(product_id:str,body:CartUpdate,db:Session=Depends(get_db),u:User=Depends(current_user)):
    item=db.query(CartItem).filter_by(user_id=u.id,product_id=product_id).first()
    if not item: raise HTTPException(404,"Cart item not found")
    p=db.get(Product,product_id)
    if body.quantity<=0: db.delete(item)
    elif body.quantity>p.stock: raise HTTPException(409,"Requested quantity is not available")
    else:item.quantity=body.quantity
    db.commit(); return {"message":"Cart updated"}
@app.delete("/api/cart/{product_id}")
def cart_remove(product_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    db.query(CartItem).filter_by(user_id=u.id,product_id=product_id).delete(); db.commit(); return {"message":"Removed"}
@app.get("/api/wishlist")
def wishlist(db:Session=Depends(get_db),u:User=Depends(current_user)):
    return [product_out(db.query(Product).options(joinedload(Product.category)).get(x.product_id)) for x in db.query(WishlistItem).filter_by(user_id=u.id).all()]
@app.post("/api/wishlist/{product_id}")
def wishlist_toggle(product_id:str,db:Session=Depends(get_db),u:User=Depends(current_user)):
    if not db.get(Product,product_id): raise HTTPException(404,"Product not found")
    item=db.query(WishlistItem).filter_by(user_id=u.id,product_id=product_id).first()
    if item:db.delete(item); saved=False
    else:db.add(WishlistItem(user_id=u.id,product_id=product_id)); saved=True
    db.commit(); return {"saved":saved}
@app.post("/api/orders/checkout")
def checkout(db:Session=Depends(get_db),u:User=Depends(current_user)):
    db=db
    try:
        rows=db.query(CartItem).filter_by(user_id=u.id).with_for_update().all()
        if not rows: raise HTTPException(400,"Your cart is empty")
        total=0; line=[]
        for row in rows:
            p=db.query(Product).filter_by(id=row.product_id).with_for_update().first()
            if not p or p.stock<row.quantity: raise HTTPException(409,f"Stock changed for {p.name if p else row.product_id}. Review your cart.")
            total+=p.price*row.quantity; line.append((p,row.quantity))
        order=Order(user_id=u.id,total=total,status="Confirmed",delivery_type="Standard")
        db.add(order); db.flush()
        for p,qty in line:
            p.stock-=qty; order.items.append(OrderItem(product_id=p.id,quantity=qty,price=p.price))
        order.events.append(ShipmentEvent(status="Order confirmed"))
        db.query(CartItem).filter_by(user_id=u.id).delete(); db.commit()
        return order_out(db.query(Order).options(joinedload(Order.items).joinedload(OrderItem.product),joinedload(Order.events)).get(order.id))
    except Exception: db.rollback(); raise
@app.get("/api/orders")
def orders(db:Session=Depends(get_db),u:User=Depends(current_user)):
    os=db.query(Order).options(joinedload(Order.items).joinedload(OrderItem.product),joinedload(Order.events)).filter_by(user_id=u.id).order_by(desc(Order.created_at)).all()
    return [order_out(o) for o in os]
@app.get("/api/orders/{order_id}")
def order_detail(order_id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    o=db.query(Order).options(joinedload(Order.items).joinedload(OrderItem.product),joinedload(Order.events)).filter_by(id=order_id,user_id=u.id).first()
    if not o: raise HTTPException(404,"Order not found")
    return order_out(o)
@app.post("/api/assistant/search")
def assistant_search(body:Ask,db:Session=Depends(get_db),u:User=Depends(current_user)):
    start=time.time(); text=body.message.strip(); llm_client=llm(); plan={}
    if llm_client:
        try:
            prompt=f'''Extract a safe product search plan from this request. Return JSON only: {{"category":"category name or empty","max_price":number or null,"min_price":number or null,"brand":"brand or empty","semantic_query":"short product preference"}}. Categories: Computers, Phones, Audio, Home, Wearables, Books, Fashion, Kitchen. Never output SQL. Request: {text}'''
            raw=llm_client.invoke(prompt).content; plan=json.loads(re.search(r"\{.*\}",str(raw),re.S).group())
        except Exception: plan={}
    # Deterministic hard-constraint extraction remains a safe fallback and SQL remains authoritative.
    money=re.search(r"(?:under|below|less than|max(?:imum)?|₹|rs\.?|inr)\s*₹?\s*([\d,]+)",text,re.I)
    if money: plan["max_price"]=float(money.group(1).replace(",",""))
    # Category filters must be explicit in the shopper's words; never trust an LLM-inferred category as a hard constraint.
    aliases={"Computers":["laptop","laptops","computer","computers","notebook","notebooks","desktop pc"],"Phones":["phone","phones","smartphone","smartphones","mobile"],"Audio":["headphones","headphone","earbuds","earbud","speakers","speaker","audio"],"Home":["air purifier","coffee maker","desk lamp","home"],"Wearables":["smartwatch","smart watch","fitness band","wearable"],"Books":["books","book","novels","novel"],"Fashion":["backpack","tote","sneaker","fashion","bag"],"Kitchen":["air fryer","kettle","cookware","mixer grinder","pan set","kitchen"],"Groceries":["grocery","groceries","coffee beans","snack","food"],"Health":["massager","massage gun","skincare","skin care","health"],"Gaming":["gaming","controller","mechanical keyboard"],"Furniture":["furniture","study desk","office chair"],"Cameras":["cameras","camera","instant cameras","instant camera"]}
    lower_text=text.lower()
    categories={c.name for c in db.query(Category).all()}
    category=next((name for name,terms in aliases.items() if name in categories and any(re.search(r"(?<![a-z0-9])"+re.escape(term)+r"(?![a-z0-9])",lower_text) for term in sorted(terms,key=len,reverse=True))),"")
    query=db.query(Product).options(joinedload(Product.category))
    if category:query=query.join(Category).filter(Category.name==category)
    if plan.get("max_price") is not None: query=query.filter(Product.price<=float(plan["max_price"]))
    if plan.get("min_price") is not None: query=query.filter(Product.price>=float(plan["min_price"]))
    if plan.get("brand"):query=query.filter(Product.brand.ilike(f"%{plan['brand']}%"))
    if any(w in text.lower() for w in ["available","in stock","deliver"]): query=query.filter(Product.stock>0)
    vector_ids=[]
    try:
        import chromadb
        collection=chromadb.PersistentClient(path=settings.chroma_path).get_or_create_collection("product_vectors")
        if collection.count()==0:
            catalog=db.query(Product).all()
            if catalog: collection.add(ids=[p.id for p in catalog],documents=[f"{p.name}. {p.description}. {p.brand}. {p.specs}" for p in catalog],metadatas=[{"product_id":p.id,"category":str(p.category_id)} for p in catalog])
        if collection.count(): vector_ids=collection.query(query_texts=[text],n_results=min(15,collection.count())).get("ids",[[]])[0]
    except Exception: vector_ids=[]
    candidates=query.order_by(desc(Product.rating)).limit(48).all()
    sem=(plan.get("semantic_query") or text).lower()
    tokens=[t for t in re.findall(r"[a-z0-9]+",sem) if len(t)>3 and t not in {"under","with","good","best","find","show","that","this","from","have","need"}]
    # Explicit numeric battery-count requests are hard requirements, not a soft similarity hint.
    # This prevents category-matching laptops from being presented as having two batteries
    # when their listing does not actually confirm that feature.
    wants_dual_battery=bool(re.search(r"\b(?:two|2|dual)\s+batter(?:y|ies)\b",text,re.I))
    scored=[]
    for p in candidates:
        hay=(p.name+" "+p.description+" "+str(p.specs)).lower()
        if wants_dual_battery and not re.search(r"\b(?:two|2|dual)\s+batter(?:y|ies)\b",hay,re.I):
            continue
        score=p.rating+sum(0.8 for t in tokens if t in hay)+(1.5 if p.id in vector_ids else 0)
        reason=p.specs.get("details",p.description)
        scored.append((score,p,reason))
    scored.sort(key=lambda x:x[0],reverse=True)
    results=[{"product":product_out(p),"reason":reason,"availability":"IN_STOCK" if p.stock else "OUT_OF_STOCK"} for _,p,reason in scored[:8]]
    clarification=("I couldn’t find a laptop listing that confirms two batteries. Would you like to see laptops with long battery life instead?" if wants_dual_battery and not results else None)
    out={"interpretedRequirement":plan.get("semantic_query",text),"budget":plan.get("max_price"),"recommendations":results,"clarifyingQuestion":clarification,"appliedFilters":{"category":category or None,"max_price":plan.get("max_price")}}
    ai_log(db,u.id,"product_search",text,out,start=start); return out
@app.post("/api/assistant/chat")
def assistant_chat(body:Ask,db:Session=Depends(get_db),u:User=Depends(current_user)):
    msg=body.message.strip(); low=msg.lower();
    if any(k in low for k in ["order","track","shipment","delivery status"]):
        os=db.query(Order).options(joinedload(Order.items).joinedload(OrderItem.product),joinedload(Order.events)).filter_by(user_id=u.id).order_by(desc(Order.created_at)).limit(5).all()
        answer="Here are your latest orders and their current tracking status." if os else "You don’t have any orders yet. Once you check out, I can help you track them here."
        out={"answer":answer,"orders":[order_out(o) for o in os],"sources":[]}
    elif any(k in low for k in ["return","refund","warranty","shipping","delivery cost","cancel","prime"]): out=policy_answer(msg,db)
    else:
        out={"answer":"I can help you discover products, answer return and delivery policy questions, or track an order. Try asking me for a product by need and budget.","sources":[]}
    ai_log(db,u.id,"assistant_chat",msg,out,out.get("sources")); return out

def policy_answer(question,db):
    # Chroma policy vectors are separate from product vectors; seeded text is indexed locally.
    sources=[]; context=[]
    try:
        import chromadb
        client=chromadb.PersistentClient(path=settings.chroma_path); col=client.get_or_create_collection("policy_documents")
        if col.count()==0:
            for i,(title,cat,body) in enumerate(policies): col.add(ids=[f"seed-{i}"],documents=[body],metadatas=[{"title":title,"category":cat,"version":"2026.1","section":cat}])
        found=col.query(query_texts=[question],n_results=min(4,col.count()))
        for doc,meta in zip(found.get("documents",[[]])[0],found.get("metadatas",[[]])[0]): context.append(doc); sources.append({"document":meta.get("title"),"section":meta.get("section"),"version":meta.get("version")})
    except Exception: context=[x[2] for x in policies if any(t in (x[0]+x[2]).lower() for t in question.lower().split())]; sources=[{"document":x[0],"section":x[1],"version":"2026.1"} for x in policies if x[2] in context]
    if not context:return {"answer":"I couldn’t find that in the approved policy documents. Please contact support for help.","confidence":"LOW","sources":[],"followUpRequired":True}
    answer=None; model=llm()
    if model:
        try: answer=str(model.invoke("Answer using only this approved policy context. If it does not answer the question, say so. Be concise. Context: "+"\n".join(context)+"\nQuestion: "+question).content)
        except Exception:pass
    if not answer:
        relevant=[x for x in context if any(t in x.lower() for t in question.lower().split() if len(t)>3)]
        answer=(relevant or context)[0] if len(context)<4 else "Based on the available policy: "+context[0]
    return {"answer":answer,"confidence":"HIGH" if sources else "MEDIUM","sources":sources,"followUpRequired":False}
@app.post("/api/admin/documents")
def upload_document(file:UploadFile=File(...),title:str="",category:str="General",version:str="2026.1",region:str="India",db:Session=Depends(get_db),u:User=Depends(current_user)):
    if u.email!="demo@shopsmart.ai": raise HTTPException(403,"Admin access required (demo account)")
    ext=Path(file.filename or "").suffix.lower()
    if ext not in {".pdf",".md",".markdown",".txt",".json"}: raise HTTPException(400,"Upload PDF, Markdown, TXT, or JSON files")
    data=file.file.read()
    if len(data)>8*1024*1024: raise HTTPException(413,"File must be under 8 MB")
    try:
        if ext==".pdf":
            from pypdf import PdfReader
            import io
            text="\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        elif ext==".json": text=json.dumps(json.loads(data.decode("utf-8")),ensure_ascii=False)
        else:text=data.decode("utf-8")
    except Exception as e: raise HTTPException(400,f"Could not read document: {e}")
    if not text.strip(): raise HTTPException(400,"No readable text found")
    chunks=[]; step=600
    for start in range(0,len(text),step):
        piece=text[start:start+700].strip()
        if piece:chunks.append(piece)
        if start+700>=len(text):break
    title=title or Path(file.filename).stem.replace("_"," ").title()
    doc=Document(title=title,category=category,version=version,region=region,chunk_count=len(chunks));db.add(doc);db.flush()
    try:
        import chromadb
        col=chromadb.PersistentClient(path=settings.chroma_path).get_or_create_collection("policy_documents")
        col.add(ids=[f"doc-{doc.id}-{i}" for i in range(len(chunks))],documents=chunks,metadatas=[{"title":title,"category":category,"version":version,"region":region,"section":category,"document_id":str(doc.id)} for _ in chunks])
    except Exception as e: db.rollback(); raise HTTPException(503,f"Vector indexing failed: {e}")
    db.commit();return {"id":doc.id,"title":doc.title,"chunk_count":doc.chunk_count,"status":"indexed"}
@app.get("/api/admin/documents")
def documents(db:Session=Depends(get_db),u:User=Depends(current_user)):
    if u.email!="demo@shopsmart.ai":raise HTTPException(403,"Admin access required")
    return [{"id":d.id,"title":d.title,"category":d.category,"version":d.version,"region":d.region,"chunk_count":d.chunk_count,"uploaded_at":d.uploaded_at.isoformat()} for d in db.query(Document).order_by(desc(Document.uploaded_at)).all()]
