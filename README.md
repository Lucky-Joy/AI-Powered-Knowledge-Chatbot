# AI-Powered Knowledge Chatbot

## Overview

This project implements an AI-powered knowledge assistant for banking operations using a Retrieval-Augmented Generation (RAG) architecture.

The system enables users to query internal documents in natural language and receive context-aware responses with source references.

---

## Key Features

* Semantic search over document collections
* Context-grounded response generation
* Source citation (document + page level)
* OCR support for scanned PDFs
* Modular and extensible architecture

---

## Important Note

This repository does **not include any document dataset**.

To run the system:

* You must **add your own documents** (PDF/DOCX/XLSX/images)
* Ingest them using the provided ingestion pipeline

The system will only return meaningful results after documents are indexed.

---

## Setup (High-Level)

1. Clone the repository
2. Install required dependencies
3. Add your documents to the ingestion pipeline
4. Run the ingestion script
5. Start the application

---

## Usage

* Launch the application (Gradio interface)
* Enter a query in natural language
* The system retrieves relevant content and generates an answer

---

## License

Copyright (c) 2026 Lucky Joy Tutika. All rights reserved.

This code may not be used, copied, modified, or distributed without explicit permission.
