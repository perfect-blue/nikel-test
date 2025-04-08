This document outlines a comprehensive design and strategy for building an efficient, scalable data warehouse architecture. The design employs a multi-layered approach that ensures data quality, security, and performance.

# Table of Content

- [Table of Content](#table-of-content)
- [Architecture Overview](#architecture-overview)
  - [Dataflow Design](#dataflow-design)
  - [Technology Stack](#technology-stack)
- [Layer Implementation](#layer-implementation)
  - [Source Data Layer](#source-data-layer)
    - [Collecting Batch Data](#collecting-batch-data)
    - [Ingesting Stream Data](#ingesting-stream-data)
      - [Performance](#performance)
      - [Further perfomance improvement](#further-perfomance-improvement)
      - [Orchestration](#orchestration)
        - [Zookeeper](#zookeeper)
        - [KRaft](#kraft)
  - [Staging Layer](#staging-layer)
      - [Handling Large Volume](#handling-large-volume)
    - [Stream Processing](#stream-processing)
  - [Core Layer](#core-layer)
  - [Analytics Layer](#analytics-layer)
    - [Pre-Aggregated Summary Tables](#pre-aggregated-summary-tables)
    - [Flattened Views for Semantic Simplicity](#flattened-views-for-semantic-simplicity)
  - [Metadata Layer](#metadata-layer)


# Architecture Overview

A modern data warehouse embraces a **modular, layer-based architecture** that cleanly separates data ingestion, transformation, storage, and consumption. This separation of concerns is not merely for organization—it directly impacts the **scalability, availability**, and **performance** of the entire system. 

True scalability isn’t just about handling more data; it’s about doing so efficiently, selectively, and without over-provisioning. High availability depends on the ability to **monitor**, **degrade gracefully**, and **recover** quickly. Performance, in turn, often comes down to resource orchestration more than raw code optimization.

Below are key design principles that reinforce these goals:
- **Separation of Concerns Enables Elastic Scaling**  
    Layers must be able to **scale independently** based on workload patterns. For example, transformation layers may need to scale out temporarily during peak ingestion windows, while reporting layers remain idle. Likewise, **components can be spun down** when not needed, reducing cost and improving system availability by minimizing unnecessary surface area.
- **Scalability Is Bidirectional**  
    The architecture must support both **scale-up** (adding resources for heavier processing) and **scale-down** (releasing compute for cost-efficiency). This flexibility is critical for systems that handle highly variable workloads—like hourly batch loads and interactive dashboards running in parallel.
- **Performance Is a Resource Management Problem**  
    Rather than relying solely on code optimization, since sometimes software engineer is more expensive than commodity computer, modern systems often improve performance by **allocating more compute or memory**—especially for I/O-heavy tasks like joins or aggregations. The ability to dynamically adjust resources is a performance enabler.
- **Shared Tools Across Layers**  
    While responsibilities are layered, the tools used need not be isolated. For instance, DuckDB or Spark may appear in both the **staging** and **reporting** layers depending on usage. Separation is about _purpose_, not always _technology_.
- **Observability Drives Availability**  
    Every data flow, ingestion checkpoint, and processing component must be **observable**. By tracking tool health and pipeline checkpoints with systems like **Prometheus** or **OpenTelemetry**, the platform ensures fast issue detection, reproducibility, and recoverability—critical components of high availability.
- **Store What Fails, Not Just What Works**  
    A robust warehouse retains **raw, failed, and partial data** alongside transformed outputs. This ensures **auditabiity**, supports **backfill** scenarios, and provides a **fallback** when transformations break or upstream data quality shifts. It also enhances incident response, making the system more resilient and available.
- **Composable Systems, Not Monoliths**  
    Modularity means you can install or use only the components relevant to a specific data context. For example, ephemeral compute for transformations doesn’t need long-running servers. This reduces operational burden and aligns with cloud-native principles of _ephemeral compute + persistent storage_.

## Dataflow Design

All data begins its lifecycle in one of two fundamental modes: **batch** or **stream**. Each mode dictates not just how data is collected but also how it's processed, stored, and orchestrated throughout the data architecture.

- **Batch processing** involves collecting data over a defined time window and processing it in bulk. This form is **time-driven**, meaning jobs run on scheduled intervals (e.g., hourly, daily). Examples include generating daily reports or aggregating system logs. While batch processing offers predictability and efficiency when working with large datasets, it naturally incurs **higher latency**, often ranging from minutes to hours. However, this delay is tolerable—and even desirable—in many use cases where data completeness is prioritized over speed.
- **Stream processing**, by contrast, is **event-driven**. Data is ingested in real time and processed with very low latency—often in **milliseconds to seconds**. It's ideal for use cases like fraud detection, real-time monitoring, and IoT telemetry. Stream processing requires a persistent **pub/sub architecture** and is designed for handling continuous data flows with low memory footprint per event, but introduces challenges in **ordering, fault tolerance**, and **exactly-once semantics**.

Batch data can arrive as **structured, semi-structured**, or even **unstructured** (e.g., CSV, JSON, logs, video). Stream data, though often semi-structured (e.g., JSON, Avro), frequently starts as **unstructured** sensor or event logs and gains schema during transformation. In both cases, data is first staged and enriched before becoming fully structured.

![[1.architecture-overview.png]]

1. **Source Layer: Batch & Stream Entry Points**  
    Batch data is handled via **Airflow**, a workflow orchestrator that schedules and manages ETL pipelines using **Python scripts**, while **Redis** provides in-memory queueing for task coordination. In parallel, stream data is managed via **Kafka**, a distributed pub/sub system known for **horizontal scalability, durability**, and strong ordering guarantees. This separation allows independent scalability and selective deployment based on use case.

2.  **Staging Layer: Buckets for Raw + Failed Data**  
    All incoming data—including raw, malformed, and failed records—is stored in **Google Cloud Storage (GCS)**. This ensures **auditabilty**, **replayability**, and **lineage tracing**. GCS is selected for its durability, lifecycle management (auto-expiry, archival), and seamless integration with Spark and BigQuery.

3. **Staging Layer: Analytics Engine for Processing**  
    If incoming data is **voluminous or computationally heavy**, it is processed via **Apache Spark** (batch and streaming modes). Spark is chosen for its distributed execution model and ability to handle structured (Spark SQL) and unstructured (Spark Streaming, MLlib) data at scale. Spark transforms raw data into a normalized, **semi-structured** format such as **Parquet** or **Avro**, ready for efficient downstream querying.

4. **Core Layer: Columnar Database for Query Performance**  
    Transformed datasets are loaded into **DuckDB**, a lightweight OLAP engine optimized for **columnar storage** and **analytical queries**. Fact and dimension modeling is employed:
    - **Fact tables** (e.g., `transaction_fact`) store transactional metrics.
    - **Dimension tables** (e.g., `account_dimension`, `time_dimension`) provide human-readable attributes for filtering and joining. This model accelerates BI queries by minimizing I/O and supporting vectorized execution.

5. **Analytics Layer: Data Marts & Visualizer**  
    DuckDB provides **data marts**—smaller, pre-joined or pre-aggregated tables optimized for reporting. These are exposed to **Tableau** or **Google Data Studio**, where dashboards are created for operational and strategic decision-making. Since data marts are pre-modeled, users avoid complex joins, improving dashboard latency and interactivity.

6. **Monitoring & Metadata: Time-Series Intelligence**  
    Every stage—from ingestion to transformation and loading—is monitored using **Prometheus**, a time-series database optimized for **high-cardinality metrics** and **real-time alerting**. It tracks:
    - Tool health (Airflow, Kafka, Spark)
    - Data freshness and latency
    - Failed pipeline retries
    - Throughput and storage usage: Time-series DBs like Prometheus are perfect for telemetry because they efficiently compress time-indexed metrics, support retention policies, and integrate with alerting tools (e.g., Grafana or Alertmanager).

The architecture is **loosely coupled**. That means:
- You can run only **batch ingestion** if streaming is not yet needed.
- You can **detach the monitoring layer** without disrupting ingestion or transformation.
- You can **replace Spark with DuckDB for small-scale data** when cost or simplicity is a concern.
- You can defer implementing audit or data cataloging without compromising basic pipeline integrity.

This **flexibility makes the architecture highly scalable and available**. You can scale horizontally by adding more Kafka partitions, Spark workers, or Airflow DAGs. Or scale down to a lean, local DuckDB + GCS pipeline for smaller projects or prototyping.

## Technology Stack
  
![[images/techstack.png]]
| Component             | Tool(s)                       | Reason                                                                 |
|----------------------|-------------------------------|------------------------------------------------------------------------|
| Workflow Manager      | Airflow, Redis                | DAG-based orchestration, scalable task execution, retry handling      |
| Stream Ingestion      | Kafka                         | Event ordering, partitioning, pub/sub decoupling, high throughput     |
| Bucket Storage        | Google Cloud Storage (GCS)    | Lifecycle rules, archive tier, Spark integration                      |
| Analytics Engine      | Apache Spark (SQL, Streaming) | Distributed compute, handles unstructured to structured transformations |
| Columnar Database     | DuckDB                        | OLAP queries, low overhead, in-process analytics, Parquet-friendly    |
| Data Visualizer       | Tableau, Google Data Studio   | Business-facing dashboards and self-service exploration               |
| Monitoring & Metadata | Prometheus                    | Time-series optimized, high resolution, flexible alerting             |
| Infrastructure & CI   | Docker, GitLab CI             | Containerized deployments, automated testing & CI/CD pipelines        |

# Layer Implementation

## Source Data Layer

### Collecting Batch Data

### Ingesting Stream Data

#### Performance

#### Further perfomance improvement

#### Orchestration
##### Zookeeper

##### KRaft

## Staging Layer

#### Handling Large Volume

### Stream Processing

## Core Layer

## Analytics Layer

### Pre-Aggregated Summary Tables

### Flattened Views for Semantic Simplicity

## Metadata Layer
