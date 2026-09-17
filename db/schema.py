"""Idempotent SQLite schema. Existing data is never dropped on startup."""

from __future__ import annotations

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS TReadUser (
        UserId INTEGER PRIMARY KEY AUTOINCREMENT,
        Username TEXT NOT NULL COLLATE NOCASE,
        Email TEXT NOT NULL COLLATE NOCASE,
        PasswordHash TEXT NOT NULL,
        Role TEXT NOT NULL DEFAULT 'User' CHECK (Role IN ('Admin', 'User')),
        IsActive INTEGER NOT NULL DEFAULT 1 CHECK (IsActive IN (0, 1)),
        MustChangePassword INTEGER NOT NULL DEFAULT 0 CHECK (MustChangePassword IN (0, 1)),
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        UpdatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        LastLoginAt TEXT,
        UNIQUE (Username),
        UNIQUE (Email)
    )
    """,
    "CREATE INDEX IF NOT EXISTS IX_TReadUser_Role ON TReadUser (Role)",
    "CREATE INDEX IF NOT EXISTS IX_TReadUser_IsActive ON TReadUser (IsActive)",
    """
    CREATE TABLE IF NOT EXISTS TPasswordReset (
        ResetId INTEGER PRIMARY KEY AUTOINCREMENT,
        UserId INTEGER NOT NULL,
        RequestedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        Status TEXT NOT NULL DEFAULT 'pending' CHECK (Status IN ('pending', 'completed', 'cancelled')),
        CompletedAt TEXT,
        FOREIGN KEY (UserId) REFERENCES TReadUser (UserId) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS IX_TPasswordReset_User ON TPasswordReset (UserId, Status)",
    """
    CREATE TABLE IF NOT EXISTS TApiProvider (
        ApiId INTEGER PRIMARY KEY AUTOINCREMENT,
        ApiCode TEXT NOT NULL UNIQUE,
        ApiName TEXT NOT NULL,
        Purpose TEXT NOT NULL,
        Category TEXT NOT NULL,
        Endpoint TEXT NOT NULL,
        IsFree INTEGER NOT NULL DEFAULT 1,
        PricingNote TEXT NOT NULL,
        FreeUsageLimit TEXT NOT NULL,
        RequiresApiKey INTEGER NOT NULL DEFAULT 0,
        IsEnabled INTEGER NOT NULL DEFAULT 1,
        FallbackApiCode TEXT,
        SortOrder INTEGER NOT NULL DEFAULT 100,
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        UpdatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS TAppSetting (
        SettingKey TEXT PRIMARY KEY,
        SettingValue TEXT,
        UpdatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS TApiUsageLog (
        UsageId INTEGER PRIMARY KEY AUTOINCREMENT,
        ApiId INTEGER NOT NULL,
        RequestUtc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        Endpoint TEXT,
        Operation TEXT NOT NULL,
        Success INTEGER NOT NULL,
        HttpStatus INTEGER,
        ResponseMs INTEGER,
        ErrorMessage TEXT,
        RateLimitRemaining TEXT,
        QuotaRemaining TEXT,
        FOREIGN KEY (ApiId) REFERENCES TApiProvider (ApiId)
    )
    """,
    "CREATE INDEX IF NOT EXISTS IX_TApiUsageLog_ApiTime ON TApiUsageLog (ApiId, RequestUtc DESC)",
    """
    CREATE TABLE IF NOT EXISTS TApiDailyUsage (
        ApiId INTEGER NOT NULL,
        UsageDate TEXT NOT NULL,
        SuccessCount INTEGER NOT NULL DEFAULT 0,
        FailureCount INTEGER NOT NULL DEFAULT 0,
        LastSuccessUtc TEXT,
        LastFailureUtc TEXT,
        LastError TEXT,
        LastHttpStatus INTEGER,
        PRIMARY KEY (ApiId, UsageDate),
        FOREIGN KEY (ApiId) REFERENCES TApiProvider (ApiId)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS TSchemaVersion (
        Version INTEGER PRIMARY KEY,
        AppliedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS TPrediction (
        PredictionId INTEGER PRIMARY KEY AUTOINCREMENT,
        UserId INTEGER NOT NULL,
        Symbol TEXT NOT NULL,
        Exchange TEXT NOT NULL DEFAULT 'NSE',
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        MarketPrice REAL,
        Horizon TEXT,
        PredictedPrice REAL,
        PriceLow REAL,
        PriceHigh REAL,
        Direction TEXT,
        Signal TEXT,
        Confidence REAL,
        StrategyVersion TEXT,
        MarketRegime TEXT,
        FeaturesJson TEXT,
        RiskLevel TEXT,
        ReasonsJson TEXT,
        ProjectionJson TEXT,
        ActualPrice REAL,
        FOREIGN KEY (UserId) REFERENCES TReadUser (UserId)
    )
    """,
    "CREATE INDEX IF NOT EXISTS IX_TPrediction_UserSymbol ON TPrediction (UserId, Symbol, CreatedAt DESC)",
    """
    CREATE TABLE IF NOT EXISTS TWorkerTask (
        TaskId INTEGER PRIMARY KEY AUTOINCREMENT,
        PublicId TEXT NOT NULL UNIQUE,
        UserId INTEGER NOT NULL,
        Source TEXT NOT NULL,
        RequestText TEXT NOT NULL,
        IntentJson TEXT,
        Symbol TEXT,
        RequiredAction TEXT,
        Priority TEXT NOT NULL DEFAULT 'normal',
        Status TEXT NOT NULL DEFAULT 'queued',
        CurrentWorker TEXT,
        PlanJson TEXT,
        StepIndex INTEGER NOT NULL DEFAULT 0,
        MarketJson TEXT,
        RiskJson TEXT,
        AuthorizationJson TEXT,
        ResultJson TEXT,
        ErrorMessage TEXT,
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        UpdatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (UserId) REFERENCES TReadUser (UserId)
    )
    """,
    "CREATE INDEX IF NOT EXISTS IX_TWorkerTask_UserStatus ON TWorkerTask (UserId, Status, CreatedAt DESC)",
    """
    CREATE TABLE IF NOT EXISTS TTaskEvent (
        EventId INTEGER PRIMARY KEY AUTOINCREMENT,
        TaskId INTEGER NOT NULL,
        WorkerCode TEXT NOT NULL,
        StepName TEXT NOT NULL,
        Status TEXT NOT NULL,
        Detail TEXT,
        PayloadJson TEXT,
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (TaskId) REFERENCES TWorkerTask (TaskId) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS IX_TTaskEvent_Task ON TTaskEvent (TaskId, EventId)",
    """
    CREATE TABLE IF NOT EXISTS TAuditLog (
        AuditId INTEGER PRIMARY KEY AUTOINCREMENT,
        UserId INTEGER,
        TaskId INTEGER,
        Action TEXT NOT NULL,
        Detail TEXT,
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS TChatMessage (
        MessageId INTEGER PRIMARY KEY AUTOINCREMENT,
        UserId INTEGER NOT NULL,
        Role TEXT NOT NULL,
        Content TEXT NOT NULL,
        Symbol TEXT,
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (UserId) REFERENCES TReadUser (UserId)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS TPaperAccount (
        UserId INTEGER PRIMARY KEY,
        CashBalance REAL NOT NULL DEFAULT 100000,
        Currency TEXT NOT NULL DEFAULT 'INR',
        UpdatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (UserId) REFERENCES TReadUser (UserId)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS TPaperOrder (
        OrderId INTEGER PRIMARY KEY AUTOINCREMENT,
        PublicId TEXT NOT NULL UNIQUE,
        UserId INTEGER NOT NULL,
        TaskId INTEGER,
        Symbol TEXT NOT NULL,
        Side TEXT NOT NULL,
        Quantity REAL NOT NULL,
        LimitPrice REAL,
        Status TEXT NOT NULL,
        FilledPrice REAL,
        Broker TEXT NOT NULL DEFAULT 'paper',
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        FOREIGN KEY (UserId) REFERENCES TReadUser (UserId)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS TApiToken (
        TokenId INTEGER PRIMARY KEY AUTOINCREMENT,
        UserId INTEGER NOT NULL,
        TokenHash TEXT NOT NULL UNIQUE,
        Label TEXT,
        CreatedAt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
        ExpiresAt TEXT NOT NULL,
        LastUsedAt TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS IX_TApiToken_User ON TApiToken (UserId, ExpiresAt)",
]

API_SEED = [
    (
        "yfinance",
        "Yahoo Finance (yfinance)",
        "Daily OHLCV from free Yahoo Finance (not a live exchange feed).",
        "Market data",
        "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
        1,
        "Unofficial public Yahoo Finance access via the yfinance library. No paid plan is used.",
        "No published quota from Yahoo for this unofficial client.",
        0,
        1,
        "stooq",
        10,
    ),
    (
        "stooq",
        "Stooq daily CSV",
        "Free fallback daily OHLCV when Yahoo Finance returns no bars.",
        "Market data",
        "https://stooq.com/q/d/l/?s={symbol}&i=d",
        1,
        "Public CSV download. No API key. Daily bars only — used as Yahoo fallback.",
        "No published request quota. Daily bars only.",
        0,
        1,
        None,
        20,
    ),
    (
        "yahoo_news",
        "Yahoo Finance News",
        "Equity and index headlines for news impact scoring.",
        "News",
        "https://finance.yahoo.com/quote/{symbol}/news",
        1,
        "Headlines from Yahoo Finance ticker pages via yfinance. No paid news API.",
        "No published quota.",
        0,
        1,
        "bbc_rss",
        30,
    ),
    (
        "bbc_rss",
        "BBC World RSS",
        "Free world headlines for macro context.",
        "News",
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        1,
        "Public RSS feed. No API key.",
        "No published quota.",
        0,
        1,
        "nyt_rss",
        40,
    ),
    (
        "nyt_rss",
        "New York Times World RSS",
        "Free world headlines (public RSS, not the paid NYT Article Search API).",
        "News",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        1,
        "Public RSS. The paid NYT Developer Article Search API is not used.",
        "No published quota.",
        0,
        1,
        None,
        50,
    ),
    (
        "local_ta",
        "Local technical indicators",
        "RSI, EMA, MACD, ATR, VWAP, Bollinger, Fibonacci computed on-device.",
        "Technical indicators",
        "local://indicators.technical",
        1,
        "No network API. Uses the open-source ta library on downloaded OHLCV.",
        "Unlimited local compute.",
        0,
        1,
        None,
        60,
    ),
    (
        "angad_internal",
        "Angad internal trading API",
        "Versioned /api/v1 services for quote, history, analysis, chat, and tasks.",
        "Internal API",
        "/api/v1",
        1,
        "First-party FastAPI layer. No third-party keys are returned to clients.",
        "60 authenticated requests per minute per token.",
        0,
        1,
        None,
        5,
    ),
    (
        "angad_knowledge",
        "Angad trading knowledge (RAG)",
        "Local markdown search for risk, indicators, data limits, and paper workers.",
        "Trading knowledge",
        "local://knowledge.search",
        1,
        "On-device TF-IDF / hybrid search. No paid embedding vendor.",
        "Unlimited local compute.",
        0,
        1,
        None,
        6,
    ),
]
