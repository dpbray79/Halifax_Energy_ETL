-- ─────────────────────────────────────────────────────────────────────────────
-- create_seed_tables.sql
-- Halifax Area Energy Demand Forecasting
-- Run this BEFORE seed_historical_data.py if tables don't exist yet
-- ─────────────────────────────────────────────────────────────────────────────

USE HalifaxEnergyProject;
GO

-- ── stg_NSP_Load ─────────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'stg_NSP_Load')
BEGIN
    CREATE TABLE stg_NSP_Load (
        LoadID      INT           IDENTITY(1,1)  PRIMARY KEY,
        DateTime    DATETIME      NOT NULL,
        Load_MW     FLOAT         NOT NULL,
        Source      VARCHAR(60)   NULL,           -- e.g. 'ElectricityMaps_CA-NS', 'CCEI_HFED'
        InsertedAt  DATETIME      DEFAULT GETDATE(),
        IsProcessed BIT           DEFAULT 0
    );
    CREATE INDEX IX_stg_NSP_Load_DateTime ON stg_NSP_Load(DateTime);
    PRINT 'Created stg_NSP_Load';
END
GO

-- ── stg_Weather ──────────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'stg_Weather')
BEGIN
    CREATE TABLE stg_Weather (
        WeatherID       INT       IDENTITY(1,1)  PRIMARY KEY,
        DateTime        DATETIME  NOT NULL,
        Temp_C          FLOAT     NULL,
        WindSpeed_kmh   FLOAT     NULL,
        Precip_mm       FLOAT     NULL,
        Humidity_Pct    FLOAT     NULL,
        Source          VARCHAR(60) NULL,
        InsertedAt      DATETIME  DEFAULT GETDATE()
    );
    CREATE INDEX IX_stg_Weather_DateTime ON stg_Weather(DateTime);
    PRINT 'Created stg_Weather';
END
GO

-- ── ETL_Watermark ─────────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'ETL_Watermark')
BEGIN
    CREATE TABLE ETL_Watermark (
        WatermarkID   INT          IDENTITY(1,1)  PRIMARY KEY,
        SourceName    VARCHAR(60)  NOT NULL UNIQUE,
        LastExtracted DATETIME     NOT NULL DEFAULT '2023-01-01',
        RowsInserted  INT          DEFAULT 0,
        Status        VARCHAR(20)  DEFAULT 'OK',
        UpdatedAt     DATETIME     DEFAULT GETDATE()
    );
    -- Pre-seed watermark rows for all sources
    INSERT INTO ETL_Watermark (SourceName, LastExtracted, Status)
    VALUES
        ('CCEI_HFED',              '2023-01-01', 'PENDING'),
        ('ElectricityMaps_CA-NS',  '2023-01-01', 'PENDING'),
        ('NBPower_NS_Interconnect', '2023-01-01', 'PENDING'),
        ('Geomet',                 '2023-01-01', 'PENDING'),
        ('OASIS_AWS',              '2023-01-01', 'PENDING');
    PRINT 'Created ETL_Watermark';
END
GO

-- ── Fact_Energy_Weather (gold table) ─────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Fact_Energy_Weather')
BEGIN
    CREATE TABLE Fact_Energy_Weather (
        FactID              INT       IDENTITY(1,1)  PRIMARY KEY,
        DateID              INT       NULL,           -- FK to Dim_Date (added by SSIS)
        DateTime            DATETIME  NOT NULL,
        Load_MW             FLOAT     NOT NULL,
        Temp_C              FLOAT     NULL,
        WindSpeed_kmh       FLOAT     NULL,
        Precip_mm           FLOAT     NULL,
        HDD_Flag            BIT       NULL,           -- Temp_C < 18
        CDD_Flag            BIT       NULL,           -- Temp_C > 22
        Lag_Load_24h        FLOAT     NULL,
        Lag_Load_168h       FLOAT     NULL,
        WindChill           FLOAT     NULL,           -- Temp_C * WindSpeed_kmh
        CommercialAreaPct   FLOAT     NULL,
        IndustrialAreaPct   FLOAT     NULL,
        Is_Holiday          BIT       DEFAULT 0,
        Hour                INT       NULL,
        DayOfWeek           INT       NULL,
        Month               INT       NULL
    );
    CREATE UNIQUE INDEX IX_Fact_DateTime ON Fact_Energy_Weather(DateTime);
    PRINT 'Created Fact_Energy_Weather';
END
GO

-- ── Dim_Date ─────────────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Dim_Date')
BEGIN
    CREATE TABLE Dim_Date (
        DateID      INT       IDENTITY(1,1)  PRIMARY KEY,
        DateTime    DATETIME  NOT NULL UNIQUE,
        Hour        INT       NOT NULL,
        DayOfWeek   INT       NOT NULL,
        Month       INT       NOT NULL,
        Year        INT       NOT NULL,
        Is_Holiday  BIT       DEFAULT 0,
        HolidayName VARCHAR(60) NULL,
        Season      VARCHAR(20) NULL   -- Spring/Summer/Fall/Winter
    );
    PRINT 'Created Dim_Date';
END
GO

-- ── Model_Predictions ─────────────────────────────────────────────────────────
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Model_Predictions')
BEGIN
    CREATE TABLE Model_Predictions (
        PredID              INT         IDENTITY(1,1)  PRIMARY KEY,
        DateID              INT         NULL,
        DateTime            DATETIME    NOT NULL,
        Predicted_Load_MW   FLOAT       NULL,
        Run_RMSE            FLOAT       NULL,
        Run_SI_Pct          FLOAT       NULL,
        ForecastHorizon     VARCHAR(10) NULL,  -- H1_24h, H2_48h, H3_7d
        ModelVersion        VARCHAR(20) NULL,
        ModelRunAt          DATETIME    DEFAULT GETDATE(),
        IsBackTest          BIT         DEFAULT 0,
        Residual_MW         AS (NULL)           -- calculated after actuals arrive
    );
    PRINT 'Created Model_Predictions';
END
GO

-- ── Useful seed validation queries ───────────────────────────────────────────
-- Run these after seed_historical_data.py to check coverage

/*
-- Row counts by source
SELECT Source, COUNT(*) AS Rows,
       MIN(DateTime) AS Earliest, MAX(DateTime) AS Latest
FROM   stg_NSP_Load
GROUP  BY Source
ORDER  BY Rows DESC;

-- Monthly coverage check
SELECT FORMAT(DateTime,'yyyy-MM') AS YearMonth,
       COUNT(*) AS HourlyRows,
       AVG(Load_MW) AS AvgLoad_MW,
       MIN(Load_MW) AS MinLoad_MW,
       MAX(Load_MW) AS MaxLoad_MW
FROM   stg_NSP_Load
GROUP  BY FORMAT(DateTime,'yyyy-MM')
ORDER  BY YearMonth;

-- Weather coverage
SELECT FORMAT(DateTime,'yyyy-MM') AS YearMonth,
       COUNT(*) AS Rows,
       AVG(Temp_C) AS AvgTemp,
       MIN(Temp_C) AS MinTemp,
       MAX(Temp_C) AS MaxTemp
FROM   stg_Weather
GROUP  BY FORMAT(DateTime,'yyyy-MM')
ORDER  BY YearMonth;

-- Gap detection (hours where no load row exists)
WITH hours AS (
    SELECT DATEADD(HOUR, n, '2023-01-01') AS hr
    FROM   (SELECT TOP 35064 ROW_NUMBER() OVER (ORDER BY (SELECT NULL))-1
            FROM sys.all_columns) t(n)
    -- 35064 = 3 years * 8760 + leap day * 24
)
SELECT h.hr AS MissingHour
FROM   hours h
LEFT   JOIN stg_NSP_Load l ON l.DateTime = h.hr
WHERE  l.LoadID IS NULL
   AND h.hr <= GETDATE()
ORDER  BY h.hr;
*/
