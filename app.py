from flask import Flask, request, jsonify, render_template
import sqlite3

app = Flask(__name__)

db_file_path = 'discobase3-29-2021-9-32-09-PM.db'

def get_db_connection():
    conn = sqlite3.connect(db_file_path)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get-actors', methods=['GET'])
def get_actors():
    conn = get_db_connection()
    actors = conn.execute('SELECT DISTINCT name FROM actors').fetchall()
    conn.close()
    actor_list = [actor['name'] for actor in actors]
    return jsonify(actor_list)

@app.route('/search-dialogues', methods=['GET'])
def search_dialogues():
    actor = request.args.get('actor', '').strip()
    keyword = request.args.get('keyword', '')
    conn = get_db_connection()
    
    if not actor:
        # If actor is empty, search across all actors
        query = """
            SELECT actors.name AS actor, actors.id AS actorid, dentries.dialoguetext AS dialogue 
            FROM dentries 
            JOIN actors ON dentries.actor = actors.id
            WHERE dentries.dialoguetext LIKE ?
        """
        results = conn.execute(query, (f"%{keyword}%",)).fetchall()
    else:
        # If actor is specified, filter by actor
        query = """
            SELECT actors.name AS actor, actors.id AS actorid, dentries.dialoguetext AS dialogue 
            FROM dentries 
            JOIN actors ON dentries.actor = actors.id
            WHERE TRIM(actors.name) = TRIM(?) COLLATE NOCASE 
            AND dentries.dialoguetext LIKE ?
        """
        results = conn.execute(query, (actor, f"%{keyword}%")).fetchall()
    
    conn.close()
    data = [{'actor': row['actor'], 'dialogue': row['dialogue']} for row in results]
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
