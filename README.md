
# Integobase API Server

Integobase is the central API and data-handling service for the Integodash ecosystem. It provides a robust backend built with FastAPI and PostgreSQL, serving as the single source of truth for all connected applications like the refactored Integodash dashboard, a future Wiki, project management tools, and more.

## Features

-   **FastAPI Backend**: A modern, high-performance Python web framework for building APIs.

-   **PostgreSQL Database**: A powerful, open-source object-relational database system for scalability and reliability.

-   **SQLAlchemy ORM**: Provides a Python-native way to interact with the database.

-   **Pydantic Data Validation**: Enforces strict data types for API inputs and outputs, reducing bugs and auto-generating documentation.

-   **RESTful API Endpoints**: A comprehensive set of endpoints for managing clients, assets, contacts, billing, knowledge base, and application settings.

-   **Integrated Data Pullers**: The data synchronization scripts from Freshservice and Datto RMM are integrated directly into the API server and run on a schedule to keep the database up-to-date.

-   **Automated Scheduler**: Uses APScheduler to periodically run the data pullers.


## Project Structure

```
integobase/
├── api/
│   └── endpoints/
│       ├── assets.py
│       ├── clients.py
│       ├── contacts.py
│       ├── knowledge_base.py
│       └── settings.py
├── data_pullers/
│   ├── pull_datto.py
│   ├── pull_freshservice.py
│   └── pull_ticket_details.py
├── .env.example
├── .gitignore
├── config.py
├── database.py
├── init_db.py
├── main.py
├── models.py
├── requirements.txt
├── schemas.py
└── scheduler.py

```

## Setup Instructions

### 1. Prerequisites

-   Python 3.8+

-   PostgreSQL Server (running and accessible)

-   Git


### 2. Installation

1.  **Clone the repository:**

    ```
    git clone <repository_url>
    cd integobase

    ```

2.  **Create a virtual environment:**

    ```
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`

    ```

3.  **Install dependencies:**

    ```
    pip install -r requirements.txt

    ```

4.  **Configure Environment Variables:**

    -   Copy the example environment file: `cp .env.example .env`

    -   Edit the `.env` file with your actual credentials for PostgreSQL, Freshservice, and Datto RMM.


    ```
    # .env
    DATABASE_URL="postgresql://user:password@host:port/dbname"
    FRESHSERVICE_DOMAIN="yourdomain.freshservice.com"
    FRESHSERVICE_API_KEY="your_freshservice_api_key"
    DATTO_API_ENDPOINT="[https://api.rmm.datto.com](https://api.rmm.datto.com)"
    DATTO_API_KEY="your_datto_public_key"
    DATTO_API_SECRET="your_datto_secret_key"

    ```


### 3. Initialize the Database

-   Make sure your PostgreSQL server is running and the user/database specified in `.env` exists and the user has permissions.

-   Run the initialization script. This will create all the necessary tables and populate them with default data.

    ```
    python init_db.py

    ```


### 4. Run the API Server

Use `uvicorn` to run the FastAPI application.

```
uvicorn main:app --reload

```

The `--reload` flag is for development and will automatically restart the server when you make code changes.

### 5. Access the API

The API will be available at `http://127.0.0.1:8000`.

You can access the auto-generated interactive API documentation (Swagger UI) at `http://127.0.0.1:8000/docs`.
