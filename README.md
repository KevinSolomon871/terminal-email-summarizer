# Terminal Email Summarizer

An automated CLI productivity utility designed to fetch and summarize unread emails across dual inboxes (college and personal) whenever a new PowerShell session starts.

## Features
- **Dual-Inbox IMAP Integration:** Connects concurrently to multiple mailboxes.
- **AI-Powered Summaries:** Uses Google's Gemini API to digest lengthy email bodies into concise, actionable bullet points.
- **Shell Automation:** Seamlessly hooks into the PowerShell startup profile (`$PROFILE`) for instant daily briefings.
- **Secure Configuration:** Separates secrets and credentials using environment variables.

## Tech Stack
- **Language:** Python 3
- **APIs & Protocols:** IMAP4, Google Gemini API
- **Shell:** PowerShell

## Setup & Configuration

1. **Clone the repository:**
   ```bash
   git clone https://github.com/KevinSolomon871/terminal-email-summarizer.git
   cd terminal-email-summarizer
   ```

2. **Install dependencies:**
   ```bash
   pip install google-generativeai python-dotenv
   ```

3. **Configure environment variables:**
   Create a `.env` file based on `.env.example.txt` and populate your credentials:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   VIT_EMAIL=your_email@vitstudent.ac.in
   VIT_PASSWORD=your_app_password
   PERSONAL_EMAIL=your_personal_email@gmail.com
   PERSONAL_PASSWORD=your_app_password
   ```

4. **PowerShell Profile Setup:**
   To run automatically on terminal launch, add the execution command from `Microsoft.PowerShell_profile.ps1` to your active profile:
   ```powershell
   notepad $PROFILE
   ```
   Append:
   ```powershell
   python "C:\path\to\terminal-email-summarizer\mail_brief.py"
   ```

## Usage
Open PowerShell. The script will authenticate, query unread messages via IMAP, format them, and print an AI-generated briefing directly to the terminal console.
