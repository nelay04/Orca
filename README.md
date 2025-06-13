* App Name:          Orca (orca2echo)
 * Description:       This is a web-based chat app
 * Version:           1.0.0
 * Framework:         Django
 * Author:            Nelay Karmakar
 * copyright:         
 * Dated:             08-11-2024
 * URL:               http://orca2echo.ddns.net/

## Project Overview

Orca is a feature-rich web-based chat application designed to provide seamless real-time communication. The project aims to deliver a user-friendly experience with robust functionality, enabling users to connect and interact effectively.

### Key Features:

*   **Real-time Chat:** Experience instant messaging with live updates, ensuring smooth and dynamic conversations.
*   **Friend System:** Connect with other users by sending and accepting friend requests, building your personal network.
*   **User Profiles:** Create and customize your user profile with personal information and avatars.
*   **OTP Authentication:** Secure your account with One-Time Password (OTP) authentication, adding an extra layer of protection.

<!-- sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server -->

<!-- uvicorn orca.asgi:application --reload --host 127.0.0.1 --port 8000 -->

## Getting Started

Follow these instructions to set up and run the Orca chat application locally.

### Prerequisites

*   Python (ensure a recent version, e.g., 3.8+ is installed)
*   Node.js and npm (for frontend asset management, check `package.json`)
*   Pip (Python package installer)
*   Redis
*   MongoDB

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```
Replace `<repository-url>` with the actual URL of the repository and `<repository-directory>` with the name of the cloned directory.

### 2. Install Dependencies

**Backend (Python):**

Navigate to the project root (where `requirements.txt` is located) and run:
```bash
pip install -r requirements.txt
```

**Frontend (Node.js):**

If `package.json` is used for frontend dependencies, navigate to the project root (or relevant frontend directory) and run:
```bash
npm install
```

### 3. Configure Databases

**SQLite:**

Django uses SQLite by default for ease of setup. The database file (`db.sqlite3`) is typically created automatically in the project root when you run migrations. Ensure you have SQLite installed on your system if it's not already.

**MongoDB:**

*   Install MongoDB on your system or use a cloud-hosted MongoDB service (e.g., MongoDB Atlas).
*   Update the MongoDB connection settings if necessary. These are typically found in `orca/settings.py` or a dedicated configuration file (e.g., within `orca2echo/services/mongo_service.py`).

**Redis:**

*   Install Redis on your system or use a cloud-hosted Redis service.
*   Ensure the Redis server is running. The application uses Redis for features like caching or real-time messaging.
    ```bash
    # Example for Debian/Ubuntu:
    sudo apt install redis-server
    sudo systemctl enable redis-server
    sudo systemctl start redis-server
    ```
*   Redis configuration details (e.g., host, port) are usually located in `orca/settings.py`.

### 4. Database Migrations (Django)

Apply database migrations to set up the schema for the Django models (primarily for SQLite):
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Run the Development Server

Start the Django development server:
```bash
python manage.py runserver
```

For development with auto-reload, especially for ASGI applications utilizing Django Channels for real-time features:
```bash
uvicorn orca.asgi:application --reload --host 127.0.0.1 --port 8000
```
The application should now be accessible at `http://127.0.0.1:8000` (or the host and port you specified).

### 6. Docker Setup (Alternative)

The project includes a `Dockerfile` and `docker-compose.yml` for easy containerized deployment.

**Build and Run with Docker Compose:**
```bash
docker-compose up --build
```
This command will build the Docker images for the application and its services (like databases, if defined in `docker-compose.yml`) and start the containers. The application should then be accessible, typically on port 8000 or as configured in `docker-compose.yml`.

**Stopping Docker Compose:**
```bash
docker-compose down
```

## Technology Stack

This project utilizes a range of modern technologies to deliver its features:

*   **Backend:**
    *   Python
    *   Django (High-level Python Web framework)
    *   Django Channels (For WebSocket and real-time support)
*   **Frontend:**
    *   HTML5
    *   CSS3
    *   JavaScript (Vanilla JS, potentially with libraries/frameworks as per `package.json`)
*   **Databases:**
    *   SQLite (Default Django database, for development or small-scale deployment)
    *   MongoDB (NoSQL database, used for specific services)
*   **Caching & Messaging:**
    *   Redis (In-memory data structure store, used for caching, session management, and message broking)
*   **Web Server/ASGI:**
    *   Uvicorn (ASGI server, for running Django Channels)
*   **Containerization:**
    *   Docker
    *   Docker Compose

## Project Structure

The project is organized as follows:

*   `.gitignore`: Specifies intentionally untracked files that Git should ignore.
*   `Dockerfile`: Defines the environment and steps to build the Docker image for the application.
*   `docker-compose.yml`: Defines and configures multi-container Docker applications using Docker Compose.
*   `entrypoint.sh`: Shell script that is often used as the entry point for the Docker container, handling initial setup.
*   `manage.py`: Django's command-line utility for administrative tasks (e.g., running the server, migrations).
*   `orca/`: Contains the main Django project configurations.
    *   `settings.py`: Django settings for the project (database, installed apps, middleware, etc.).
    *   `urls.py`: Root URL configurations for the project, mapping URLs to views or other URL files.
    *   `asgi.py`: ASGI configuration for Django Channels, enabling asynchronous features.
    *   `wsgi.py`: WSGI configuration for traditional synchronous HTTP requests.
*   `orca2echo/`: This is the primary Django app that houses the chat application's core logic.
    *   `models.py`: Defines the database schema through Django models.
    *   `views.py`: Contains the view functions/classes that handle HTTP requests and responses.
    *   `consumers.py`: Holds WebSocket consumers for handling real-time communication via Django Channels.
    *   `services/`: Contains modules for business logic, such as:
        *   `auth_service.py`: Handles authentication logic.
        *   `model_service.py`: Provides services related to data models.
        *   `mongo_service.py`: Manages interactions with MongoDB.
    *   `static/`: Stores static assets like CSS stylesheets, JavaScript files, and images.
    *   `templates/`: Contains HTML templates rendered by Django views.
    *   `routing.py`: Defines the routing for WebSocket connections to consumers.
    *   `urls.py`: Contains URL patterns specific to the `orca2echo` app.
*   `package.json`: Lists JavaScript dependencies and scripts for frontend development (managed via npm or yarn).
*   `README.md`: This file, providing an overview and guide to the project.
*   `requirements.txt`: Lists the Python packages required for the project (managed via pip).
*   `db.sqlite3`: The SQLite database file (default for Django development, typically created after running migrations).

## Contributing

Contributions are welcome and greatly appreciated! Whether it's reporting a bug, suggesting a feature, or contributing code, your help is valuable.

### General Guidelines

If you'd like to contribute code, please follow these general steps:

1.  **Fork the Repository:** Start by forking the project repository to your own GitHub account.
2.  **Create a New Branch:** Create a new branch from the `main` (or `develop`) branch for your changes. Choose a descriptive branch name (e.g., `feat/add-new-feature` or `fix/resolve-bug-xyz`).
    ```bash
    git checkout -b your-branch-name
    ```
3.  **Make Your Changes:** Implement your feature or bug fix. Ensure your code follows the project's coding style and conventions.
4.  **Commit Your Changes:** Commit your changes with a clear and concise commit message.
    ```bash
    git commit -m "Brief description of your changes"
    ```
5.  **Push to Your Fork:** Push your changes to your forked repository.
    ```bash
    git push origin your-branch-name
    ```
6.  **Submit a Pull Request:** Open a pull request (PR) from your branch to the original project's `main` (or `develop`) branch. Provide a detailed description of your changes in the PR.

### Reporting Bugs or Suggesting Features

*   **Bugs:** If you encounter a bug, please open an issue on the project's GitHub issue tracker. Include steps to reproduce the bug, expected behavior, and actual behavior.
*   **Features:** If you have an idea for a new feature or an enhancement to an existing one, feel free to open an issue to discuss it. Provide a clear description of the proposed feature and its potential benefits.

We appreciate your efforts to help improve Orca!

## License

This project is currently not licensed. It is recommended to choose an open-source license that suits the project's goals.

For example, you could consider adding an [MIT License](https://opensource.org/licenses/MIT), which is a permissive free software license originating at the Massachusetts Institute of Technology (MIT).
