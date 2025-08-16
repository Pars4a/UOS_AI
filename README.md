# Haawall Bot - University of Sulaimani AI Assistant

Your Academic Journey Companion

Haawall Bot is an AI-powered assistant designed to support university students by providing fast and accurate answers to general questions—anytime, anywhere.

## 🎯 Problem
During major college events or registration periods, staff often become overwhelmed by a flood of student questions. This can lead to delays, miscommunication, and frustration on both sides.

So, what if we had a centralized platform—better yet, an AI chatbot—that could instantly respond to students' questions and lighten the load on university staff?

Haawall Bot is our answer to that need. It brings automation, clarity, and efficiency to student support.

## 🚀 Product Impact
- Reduces the pressure on college administration and staff
- Ensures students get faster and more accurate information
- Acts as a central information hub for the entire university
- Introduces modern, smart technology to our top-tier university

## 🌍 Our Vision for the Future
While Haawall Bot currently provides general-purpose answers, our vision is to evolve it into a complete academic companion.

Future features include:
- Personalized academic progress tracking
- Integration with university systems
- Lecturer-assisted responses
- Course recommendations and schedules

## 🧠 And beyond...
Haawall Bot is just the beginning. We aim to grow this project into the largest Kurdish AI center—a hub for innovation in education, automation, and intelligent systems.
This platform will be the foundation for future Kurdish-language AI solutions, contributing to the region's digital transformation.

## 🔐 Admin Access
**Admin Credentials:**
- Email: `admin@uos.edu.krd`
- Password: `UOS_Admin_2024!`

Access the admin dashboard at `/login` to manage users, view chat history, and system settings.

## 🛠️ Technical Stack
- **Backend**: FastAPI with Python
- **Frontend**: HTML, CSS, JavaScript
- **Database**: PostgreSQL with SQLAlchemy
- **AI**: Claude API (Anthropic) with OpenAI fallback
- **Authentication**: JWT tokens with role-based access
- **Deployment**: Docker containers with Kubernetes support

## 🚀 Getting Started

### Prerequisites
- Docker and Docker Compose
- Python 3.12+
- PostgreSQL

### Environment Setup
1. Clone the repository
2. Create a `.env` file with your API keys:
```env
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=your_database
ADMIN_TOKEN=your_admin_token
SENDER_EMAIL=your_email
SENDER_PASSWORD=your_email_password
```

### Running the Application
```bash
# Using Docker Compose
docker compose up --build

# Or run the setup script
chmod +x scripts/first_setup.sh
./scripts/first_setup.sh
```

The application will be available at:
- Main app: http://localhost:5000
- API: http://localhost:8000
- Admin dashboard: http://localhost:8000/dashboard

## 📁 Project Structure
```
├── backend/           # FastAPI backend
├── frontend/          # HTML/CSS/JS frontend
├── k8s/              # Kubernetes configurations
├── scripts/          # Utility scripts
├── tests/            # Test files
└── compose.yaml      # Docker Compose configuration
```

## 🔧 Features
- **Multi-language Support**: English and Kurdish
- **Authentication System**: User registration, login, guest mode
- **Admin Dashboard**: User management, chat history, system controls
- **Real-time Chat**: AI-powered responses with fallback systems
- **Responsive Design**: Mobile-friendly interface
- **Rate Limiting**: Protection against abuse
- **Email Integration**: Contact form and notifications

## 🤝 Contributing
We welcome contributions! Please feel free to submit issues and pull requests.

## 📄 License
This project is part of the University of Sulaimani Computer Engineering Department.

---
Made with ❤️ for the University of Sulaimani community