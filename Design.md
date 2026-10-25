# ShopSmart AI — System Design

ShopSmart AI is an AI-assisted shopping application with a React/Vite frontend, FastAPI backend, SQLAlchemy/SQLite relational storage, Gemini-powered language-model operations, and ChromaDB retrieval for policy documents. This document captures the system architecture and four core workflows in GitHub-renderable Mermaid.

> **Implementation status:** The diagrams combine the project structure discussed so far with proposed enhancements. In particular, a dedicated product-vector collection and schema-aware hybrid product retrieval are proposed additions, not assumed to exist in the current code. Confirm names, routes, and behavior against the repository before treating this document as a source-of-truth implementation specification.

## Contents

- [High-Level Design](#1-high-level-design-hld)
- [Low-Level Design](#2-low-level-design-lld)
- [Entity Relationship Diagram](#3-entity-relationship-diagram-erd)
- [Workflow 1: Shopping and Checkout](#4-workflow-1-shopping-and-checkout)
- [Workflow 2: LLM-Driven Hybrid Product Search](#5-workflow-2-llm-driven-hybrid-product-search)
- [Workflow 3: Policy Document Ingestion](#6-workflow-3-policy-document-ingestion)
- [Workflow 4: Policy RAG Question Answering](#7-workflow-4-policy-rag-question-answering)
- [Design and Security Notes](#8-design-and-security-notes)
- [Repository Layout](#9-repository-layout)

## 1. High-Level Design (HLD)

The HLD shows the user-facing application, API layer, business services, AI provider, and persistence systems.

```mermaid
flowchart TB
    User["Customer / Admin"]
    subgraph FE["Frontend — React 19 + Vite"]
        Catalog["Product Catalog & Search"]
        Compare["Product Comparison"]
        Cart["Cart"]
        Wishlist["Wishlist"]
        Orders["Order History"]
        ShopUI["AI Shopping Assistant"]
        PolicyUI["Policy Assistant"]
        DocsUI["Document Management"]
    end
    subgraph API["Backend — FastAPI"]
        AuthAPI["Authentication API"]
        ProductAPI["Product API"]
        CartAPI["Cart API"]
        WishlistAPI["Wishlist API"]
        OrderAPI["Orders API"]
        AssistantAPI["Assistant API"]
        DocumentAPI["Document API"]
        subgraph Services["Application Services"]
            ProductService["Product Service"]
            OrderService["Order Service"]
            ShoppingAgent["Schema-aware Shopping Agent"]
            RAGService["Policy RAG Service"]
            LLMService["Gemini / Embedding Service"]
        end
    end
    Gemini["Google Gemini API"]
    SQL[("SQLite + SQLAlchemy")]
    ProductVectors[("ChromaDB — Product Vectors")]
    PolicyVectors[("ChromaDB — Policy Vectors")]
    Files[("Uploaded Policy Files")]

    User --> Catalog
    User --> ShopUI
    User --> PolicyUI
    Catalog --> ProductAPI
    Compare --> ProductAPI
    Cart --> CartAPI
    Wishlist --> WishlistAPI
    Orders --> OrderAPI
    ShopUI --> AssistantAPI
    PolicyUI --> AssistantAPI
    DocsUI --> DocumentAPI
    AuthAPI --> SQL
    ProductAPI --> ProductService
    ProductService --> SQL
    CartAPI --> SQL
    WishlistAPI --> SQL
    OrderAPI --> OrderService
    OrderService --> SQL
    AssistantAPI --> ShoppingAgent
    ShoppingAgent --> SQL
    ShoppingAgent --> ProductVectors
    ShoppingAgent --> LLMService
    AssistantAPI --> RAGService
    DocumentAPI --> RAGService
    RAGService --> PolicyVectors
    RAGService --> Files
    RAGService --> SQL
    RAGService --> LLMService
    LLMService --> Gemini
```

## 2. Low-Level Design (LLD)

This view separates API routers, application services, core infrastructure, models/schemas, and external stores.

```mermaid
flowchart TB
    Client["React Frontend"] --> Middleware["FastAPI routing / CORS"]
    subgraph Routers["API Routers"]
        AuthRouter["auth.py"]
        ProductRouter["products.py"]
        CartRouter["cart.py"]
        WishlistRouter["wishlist.py"]
        OrderRouter["orders.py"]
        AssistantRouter["assistant.py"]
        DocumentRouter["documents.py"]
    end
    subgraph Services["Business Services"]
        ProductService["product_service.py"]
        OrderService["order_service.py"]
        ShoppingAgent["shop_agent.py — schema-aware retrieval"]
        RAGService["rag_service.py"]
        LLMService["llm.py"]
    end
    subgraph Core["Core / Validation"]
        Security["security.py"]
        Config["config.py"]
        DBSession["database.py — DB session"]
        Schemas["Pydantic request/response schemas"]
        Models["db_models.py — SQLAlchemy models"]
        QueryGuard["Query-plan validator / allowlist"]
    end
    SQL[("SQLite")]
    ProductVectors[("ChromaDB product collection — proposed")]
    PolicyVectors[("ChromaDB policy collection")]
    Gemini["Gemini API"]
    PolicyFiles["Policy document files"]

    Middleware --> AuthRouter
    Middleware --> ProductRouter
    Middleware --> CartRouter
    Middleware --> WishlistRouter
    Middleware --> OrderRouter
    Middleware --> AssistantRouter
    Middleware --> DocumentRouter
    AuthRouter --> Security
    AuthRouter --> Models
    ProductRouter --> ProductService
    CartRouter --> Models
    WishlistRouter --> Models
    OrderRouter --> OrderService
    AssistantRouter --> ShoppingAgent
    AssistantRouter --> RAGService
    DocumentRouter --> RAGService
    ProductService --> Models
    OrderService --> Models
    ShoppingAgent --> QueryGuard
    QueryGuard --> Models
    ShoppingAgent --> ProductVectors
    ShoppingAgent --> LLMService
    RAGService --> PolicyVectors
    RAGService --> PolicyFiles
    RAGService --> Models
    RAGService --> LLMService
    LLMService --> Gemini
    Models --> DBSession
    DBSession --> SQL
    Config -.-> Security
    Config -.-> LLMService
    Schemas -.-> AssistantRouter
```

## 3. Entity Relationship Diagram (ERD)

The ERD reflects the discussed SQLAlchemy entities. `AI_LOGS.user_id` is intentionally not connected to `USERS` because the current model was described as not declaring it as a foreign key. The cart and wishlist models have unique `(user_id, product_id)` constraints.

```mermaid
erDiagram
    USERS ||--o{ CART_ITEMS : has
    USERS ||--o{ WISHLIST_ITEMS : saves
    USERS ||--o{ ORDERS : places
    CATEGORIES o|--o{ CATEGORIES : parent_of
    CATEGORIES ||--o{ PRODUCTS : contains
    PRODUCTS ||--o{ CART_ITEMS : appears_in
    PRODUCTS ||--o{ WISHLIST_ITEMS : saved_in
    PRODUCTS ||--o{ ORDER_ITEMS : purchased_as
    ORDERS ||--|{ ORDER_ITEMS : contains
    ORDERS ||--o{ SHIPMENT_EVENTS : tracks

    USERS {
        int id PK
        string name
        string email
        string password_hash
        string membership_tier
        json preferences
    }
    CATEGORIES {
        int id PK
        string name
        int parent_id FK
    }
    PRODUCTS {
        string id PK
        string name
        int category_id FK
        string brand
        text description
        float price
        float rating
        int stock
        text image_url
        json specs
    }
    CART_ITEMS {
        int id PK
        int user_id FK
        string product_id FK
        int quantity
    }
    WISHLIST_ITEMS {
        int id PK
        int user_id FK
        string product_id FK
    }
    ORDERS {
        int id PK
        int user_id FK
        float total
        string status
        string delivery_type
        datetime created_at
    }
    ORDER_ITEMS {
        int id PK
        int order_id FK
        string product_id FK
        int quantity
        float price
    }
    SHIPMENT_EVENTS {
        int id PK
        int order_id FK
        string status
        datetime timestamp
    }
    DOCUMENTS {
        int id PK
        string title
        string doc_type
        string version
        string effective_date
        string category
        string region
        int chunk_count
        datetime uploaded_at
    }
    AI_LOGS {
        int id PK
        string endpoint
        int user_id
        text query
        json response_json
        json sources_json
        int latency_ms
        datetime created_at
    }
```

## 4. Workflow 1: Shopping and Checkout

The workflow validates the cart again at checkout. In production, order creation, order-item insertion, and stock deduction should run in a transaction with safe concurrency controls.

```mermaid
flowchart TD
    Start([Start]) --> Login["User logs in"]
    Login --> Auth{"Credentials valid?"}
    Auth -- No --> AuthError["Show authentication error"]
    AuthError --> Login
    Auth -- Yes --> Browse["Browse/search products"]
    Browse --> View["View product details"]
    View --> Add["Add product to cart"]
    Add --> Stock{"Stock available?"}
    Stock -- No --> StockError["Show stock error"]
    StockError --> Browse
    Stock -- Yes --> Cart["Update cart"]
    Cart --> Review["Review cart"]
    Review --> Checkout["Submit checkout"]
    Checkout --> Revalidate["Revalidate quantities and stock"]
    Revalidate --> Valid{"Cart valid?"}
    Valid -- No --> Fix["Return validation error"]
    Fix --> Review
    Valid -- Yes --> Tx["Begin database transaction"]
    Tx --> Order["Create order and order items"]
    Order --> Reduce["Safely decrement stock"]
    Reduce --> Event["Create initial shipment event"]
    Event --> Commit["Commit transaction"]
    Commit --> Success["Return order confirmation"]
    Success --> End([End])
    Reduce -. "On failure: rollback" .-> Rollback["Rollback transaction"]
    Rollback --> Fix
```

## 5. Workflow 2: LLM-Driven Hybrid Product Search

Example question: **“Find all laptops under ₹70,000 with an OLED screen that are good for programming.”**

1. Provide Gemini with the user question, approved schema metadata, allowed fields/operators, and the expected structured output.
2. Gemini returns a **query plan**, not unrestricted database permissions. The plan separates exact filters from semantic preferences.
3. Validate every field, operator, value type, limit, and sort option.
4. Use parameterized SQLAlchemy expressions for exact conditions such as price, category, stock, and structured screen type.
5. If semantic matching is needed, query a **separate product-vector collection**. This collection must be created and populated; the existing policy-vector collection is not a product index.
6. Merge candidates and reapply hard constraints using authoritative database values.
7. Optionally use Gemini to rank only eligible candidate IDs. Validate IDs and fetch final product details from SQL.

```mermaid
flowchart TD
    Start([Natural-language product question]) --> API["FastAPI Assistant API"]
    API --> Schema["Load approved schema, fields, relationships and operators"]
    Schema --> LLM["LLM interprets question"]
    LLM --> Plan["Return structured query plan + semantic query"]
    Plan --> Validate{"Plan valid and fields allowed?"}
    Validate -- No --> Clarify["Clarify request or return safe validation error"]
    Clarify --> End([End])
    Validate -- Yes --> Split["Separate hard filters from semantic preferences"]
    Split --> SQLPlan["Build parameterized SQLAlchemy query"]
    SQLPlan --> SQL[("SQLite product catalog")]
    SQL --> SQLCandidates["Products matching hard filters"]
    Split --> Semantic{"Semantic search needed?"}
    Semantic -- Yes --> Embed["Embed semantic query"]
    Embed --> ProductVector[("Product vector collection")]
    ProductVector --> VectorCandidates["Retrieve semantic candidates"]
    Semantic -- No --> SkipVector["Use structured candidates only"]
    SQLCandidates --> Merge["Merge and deduplicate candidate IDs"]
    VectorCandidates --> Merge
    SkipVector --> Merge
    Merge --> Verify["Reapply hard filters and verify specifications against SQL"]
    Verify --> Found{"Eligible products found?"}
    Found -- No --> None["Return no-match response"]
    None --> End
    Found -- Yes --> Rank["Optionally rank eligible candidate IDs with LLM"]
    Rank --> ValidateIDs["Reject IDs outside eligible candidate set"]
    ValidateIDs --> Authoritative["Fetch final names, prices, specs and stock from SQL"]
    Authoritative --> Response["Return products, reasons and applied filters"]
    Response --> Audit["Write AI audit log"]
    Audit --> Done([Return results])
```

### Example query-plan contract

This is an illustrative JSON contract; adapt field names to the actual schema and categories.

```json
{
  "intent": "product_search",
  "filters": [
    {"field": "category_id", "operator": "category_equals", "value": "laptop"},
    {"field": "price", "operator": "lte", "value": 70000},
    {"field": "specs.screen_type", "operator": "equals", "value": "OLED"},
    {"field": "stock", "operator": "gt", "value": 0}
  ],
  "semantic_query": "Laptop suitable for programming",
  "semantic_search_enabled": true,
  "top_k": 10,
  "sort": "relevance"
}
```

**Security rules:** never execute arbitrary LLM text as SQL; use an allowlist and typed query plan, parameterized SQLAlchemy filters, read-only access for search, query timeouts/limits, and authoritative post-filtering. The LLM should not receive database credentials or unrestricted tool access.

## 6. Workflow 3: Policy Document Ingestion

This workflow indexes policy files for later RAG retrieval. The discussed splitter uses approximately 700-character chunks with 100-character overlap; metadata includes document identity and relevant source attributes.

```mermaid
flowchart TD
    Start([Admin uploads policy document]) --> Validate["Validate extension, size and access"]
    Validate --> Valid{"File allowed?"}
    Valid -- No --> Reject["Reject upload with clear error"]
    Reject --> End([End])
    Valid -- Yes --> Parse["Extract text from PDF, Markdown, TXT or JSON"]
    Parse --> Text{"Text extracted?"}
    Text -- No --> ParseError["Report parsing failure"]
    ParseError --> End
    Text -- Yes --> Chunk["Split into overlapping chunks; preserve headings where possible"]
    Chunk --> Embed["Generate embeddings"]
    Embed --> EmbeddingsOK{"Embedding generation successful?"}
    EmbeddingsOK -- No --> EmbedError["Report ingestion failure; don't mark indexed"]
    EmbedError --> End
    EmbeddingsOK -- Yes --> StoreVectors["Store chunks and source/version/category/region metadata in ChromaDB"]
    StoreVectors --> StoreMetadata["Persist document metadata and chunk count in SQLite"]
    StoreMetadata --> Complete([Document indexed])
```

## 7. Workflow 4: Policy RAG Question Answering

This workflow is separate from product semantic search. It retrieves policy passages, uses them as grounded context, and returns source metadata.

```mermaid
flowchart TD
    Start([User asks a policy question]) --> Validate["Validate request and permissions"]
    Validate --> Embed["Embed question"]
    Embed --> Search["Similarity search in policy ChromaDB"]
    Search --> Retrieve["Retrieve top relevant chunks"]
    Retrieve --> Threshold{"Relevance threshold met?"}
    Threshold -- No --> Fallback["Return safe 'not found in available policy' response"]
    Fallback --> Return([Return answer])
    Threshold -- Yes --> Context["Build context with source metadata"]
    Context --> Prompt["Ask Gemini to answer only from supplied context"]
    Prompt --> ModelOK{"Model response usable?"}
    ModelOK -- No --> Fallback
    ModelOK -- Yes --> Sources["Attach document title, section/version and source references"]
    Sources --> Audit["Log query, response, sources and latency"]
    Audit --> Return
```

## 8. Design and Security Notes

- **Two vector-search domains:** keep product embeddings and policy-document embeddings logically separate, even if both use ChromaDB.
- **Hard filters are authoritative:** price ceilings, stock availability, brand constraints, and structured attributes must be verified against SQL before results are returned.
- **Schema exposure:** give the LLM only the schema metadata needed for query planning. Do not send credentials or the entire database.
- **Structured output:** prefer a typed JSON query plan over raw SQL. Validate table/column allowlists, operators, types, limits, and sorting.
- **Semantic retrieval is optional:** queries consisting entirely of exact filters may not need vector search.
- **Fallbacks:** handle unavailable LLM/embeddings, invalid plans, no results, vector-store failures, and insufficient RAG context.
- **Checkout consistency:** use transactions and concurrency-safe stock updates.
- **Auditability:** record the query, selected filters, retrieval sources, latency, and response metadata while avoiding unnecessary sensitive data.
- **Demo boundaries:** payment processing and carrier integrations are not represented as live integrations.

## 9. Repository Layout

```text
ShopSmartAI/
├── README.md
└── docs/
    └── diagrams/
        ├── hld.mmd
        ├── lld.mmd
        ├── erd.mmd
        ├── workflow-1-checkout.mmd
        ├── workflow-2-ai-hybrid-search.mmd
        ├── workflow-3-policy-ingestion.mmd
        └── workflow-4-policy-rag-query.mmd
```

GitHub renders Mermaid diagrams embedded in Markdown fences. The `.mmd` files keep the source diagrams separate and reusable; copy a diagram into a ` ```mermaid ` block in the README when you want it rendered inline.
