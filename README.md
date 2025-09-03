
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
    
-   Git
    
-   PostgreSQL Server (running and accessible)
    

### 2. PostgreSQL Server Setup

You need a running PostgreSQL server before you can initialize the application database.

#### For Ubuntu (Recommended for Development)

Since you're comfortable with Linux, these are the typical steps for a new installation.

1.  **Install PostgreSQL:**
    
    ```
    sudo apt update
    sudo apt install postgresql postgresql-contrib
    
    ```
    
2.  **Start and Enable the Service:**
    
    ```
    sudo systemctl start postgresql
    sudo systemctl enable postgresql
    
    ```
    
3.  **Create a Database User and Database:** The application needs its own user and database. Access the PostgreSQL prompt as the default `postgres` user.
    
    ```
    sudo -u postgres psql
    
    ```
    
    Now, run the following SQL commands. **Remember to replace `'your_secure_password'` with the actual password** you will set in your `.env` file.
    
    ```
    -- Create a new user (role) for the application
    CREATE USER integobash_user WITH PASSWORD 'your_secure_password';
    
    -- Create the database for the application
    CREATE DATABASE integobase_db;
    
    -- Grant all privileges on the new database to the new user
    GRANT ALL PRIVILEGES ON DATABASE integobase_db TO integobash_user;
    ALTER DATABASE integobase_db OWNER TO integobash_user;
    
    -- Exit the psql prompt
    \q
    
    ```
    

#### For Windows

1.  **Download the Installer:** Go to the [official PostgreSQL website](https://www.postgresql.org/download/windows/ "null") and download the interactive installer from EDB.
    
2.  **Run the Installer:**
    
    -   Run the downloaded installer. You can accept the default settings for most steps.
        
    -   **Important:** During installation, you will be prompted to set a password for the superuser (`postgres`). **Remember this password.**
        
    -   You can skip installing "Stack Builder" at the end of the installation.
        
3.  **Create a Database User and Database:** You can use the graphical tool `pgAdmin 4` (which is installed automatically) or the command-line `SQL Shell (psql)`.
    
    **Using pgAdmin 4:**
    
    -   Open pgAdmin 4.
        
    -   Connect to your local server (it will ask for the `postgres` password you set during installation).
        
    -   In the browser tree on the left, right-click on **Login/Group Roles** -> **Create** -> **Login/Group Role...**.
        
        -   In the "General" tab, enter the name `integobash_user`.
            
        -   In the "Definition" tab, enter and confirm a secure password.
            
        -   In the "Privileges" tab, grant "Can login?" permissions.
            
        -   Click **Save**.
            
    -   Right-click on **Databases** -> **Create** -> **Database...**.
        
        -   Enter the Database name `integobase_db`.
            
        -   Set the Owner to the `integobash_user` you just created.
            
        -   Click **Save**.
            
    
    **Using SQL Shell (psql):**
    
    -   Open "SQL Shell (psql)" from your Start Menu.
        
    -   Press Enter for the default Server, Database, Port, and Username. It will then prompt for the `postgres` user's password.
        
    -   Run the same SQL commands as in the Ubuntu guide:
        
        ```
        CREATE USER integobash_user WITH PASSWORD 'your_secure_password';
        CREATE DATABASE integobase_db;
        GRANT ALL PRIVILEGES ON DATABASE integobase_db TO integobash_user;
        ALTER DATABASE integobase_db OWNER TO integobash_user;

        \q
        
        ```
        

### 3. Application Installation

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
        
    -   Edit the `.env` file with your credentials. **Ensure the `DATABASE_URL` matches the user, password, and database you created in the PostgreSQL setup step.**
        
    
    ```
    # .env
    DATABASE_URL="postgresql://integobash_user:your_secure_password@localhost:5432/integobase_db"
    FRESHSERVICE_DOMAIN="yourdomain.freshservice.com"
    FRESHSERVICE_API_KEY="your_freshservice_api_key"
    DATTO_API_ENDPOINT="[https://api.rmm.datto.com](https://api.rmm.datto.com)"
    DATTO_API_KEY="your_datto_public_key"
    DATTO_API_SECRET="your_datto_secret_key"
    
    ```
    

### 4. Initialize the Application Database

-   Make sure your PostgreSQL server is running.
    
-   Run the initialization script. This will connect to your PostgreSQL server and create all the necessary tables inside the `integobase_db` database.
    
    ```
    python init_db.py
    
    ```
    

### 5. Run the API Server

Use `uvicorn` to run the FastAPI application.

```
uvicorn main:app --reload

```

The `--reload` flag is for development and will automatically restart the server when you make code changes.

### 6. Access the API

The API will be available at `http://127.0.0.1:8000`.

You can access the auto-generated interactive API documentation (Swagger UI) at `http://127.0.0.1:8000/docs`.
