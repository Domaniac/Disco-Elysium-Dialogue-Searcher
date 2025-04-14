# Disco Elysium Dialogue Searcher
 
Purpose:
Small Python flask project to find dialogue lines from Disco Elysium Final Cut Edition. This is run locally.
This is mainly used when I want to find Disco Elysium lines and https://fayde.co.uk/ is down. This is a much simpler program compared to that. This is for personal use and not in active development.

Features:
Filter lines from Disco Elysium by Actors and dialogue keywords

Instructions:
1) Install Python 3.11. Verify the installation by running `python --version` in your terminal/cmd.
2) Clone this repo
3) Navigate to the directory where the repo is located in terminal/cmd.
4) Create a virtual environment by typing: `python -m venv [your environment name here]`.
5) Activate the virtual environment by typing: `.\[your environment name here]\Scripts\activate`
6) Install required dependencies by typing: `pip install -r requirements.txt`.
7) Download the final cut DB from https://fayde.seadragonlair.co.uk/ . Ensure the database file is in the same directory as `app.py`.
8) Run the app by typing: `flask run`. The app will be accessible at `http://127.0.0.1:5000/`.


Contact: Feel free to email me at contact@domloh.com for anything regarding this project.