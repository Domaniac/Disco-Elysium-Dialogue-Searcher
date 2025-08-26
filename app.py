from flask import Flask, request, jsonify, render_template
import sqlite3

app = Flask(__name__)

db_file_path = 'discobase3-29-2021-9-32-09-PM.db'

def get_db_connection():
    conn = sqlite3.connect(db_file_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_actual_difficulty_and_label(db_difficulty):
    """
    Convert database difficulty to actual game difficulty and label.
    Based on the mapping found in conversation 1428 in the database.
    """
    # The actual mapping from the database
    difficulty_mapping = {
        0: (6, "Trivial"),
        1: (8, "Easy"), 
        2: (10, "Normal"),
        3: (12, "Challenging"),
        4: (14, "Difficult"),
        5: (16, "Very Difficult"),
        6: (18, "Heroic"),
        7: (20, "Impossible"),
        8: (7, "Easy"),
        9: (9, "Normal"),
        10: (11, "Challenging"),
        11: (13, "Difficult"),
        12: (15, "Very Difficult"),
        13: (17, "Heroic"),
        14: (19, "Impossible")
    }
    
    if db_difficulty in difficulty_mapping:
        return difficulty_mapping[db_difficulty]
    else:
        # Fallback for unknown values
        return (db_difficulty, "Unknown")

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

@app.route('/get-all-actors', methods=['GET'])
def get_all_actors():
    conn = get_db_connection()
    # Get all actors with their dialogue counts
    query = """
        SELECT actors.name AS actor, 
               COUNT(dentries.id) AS dialogue_count
        FROM actors 
        LEFT JOIN dentries ON actors.id = dentries.actor
        GROUP BY actors.id, actors.name
        ORDER BY dialogue_count DESC, actors.name ASC
    """
    results = conn.execute(query).fetchall()
    conn.close()
    
    data = [{'actor': row['actor'], 'dialogue_count': row['dialogue_count']} for row in results]
    return jsonify(data)

@app.route('/get-dialogue-connections', methods=['GET'])
def get_dialogue_connections():
    conversation_id = request.args.get('conversationid')
    dialogue_id = request.args.get('dialogueid')
    
    if not conversation_id or not dialogue_id:
        return jsonify({'error': 'Missing conversationid or dialogueid'}), 400
    
    conn = get_db_connection()
    
    # Get skill checks
    checks = conn.execute("""
        SELECT difficulty, skilltype, isred, flagname
        FROM checks 
        WHERE conversationid = ? AND dialogueid = ?
    """, (conversation_id, dialogue_id)).fetchall()
    
    # Get alternate text
    alternates = conn.execute("""
        SELECT condition, alternateline
        FROM alternates 
        WHERE conversationid = ? AND dialogueid = ?
    """, (conversation_id, dialogue_id)).fetchall()
    
    # Get connected dialogues
    links = conn.execute("""
        SELECT dl.destinationconversationid, dl.destinationdialogueid, dl.priority, dl.isConnector,
               d.dialoguetext, a.name as actor, d.hascheck, d.conditionstring
        FROM dlinks dl
        JOIN dentries d ON dl.destinationconversationid = d.conversationid AND dl.destinationdialogueid = d.id
        JOIN actors a ON d.actor = a.id
        WHERE dl.originconversationid = ? AND dl.origindialogueid = ?
        ORDER BY dl.priority DESC
    """, (conversation_id, dialogue_id)).fetchall()
    
    # Enhanced skill check outcome tracking
    skill_outcomes = []
    for check in checks:
        if check['flagname']:
            # Method 1: Find connector entries that check the flag
            connectors = conn.execute("""
                SELECT dl.destinationconversationid, dl.destinationdialogueid, d.conditionstring
                FROM dlinks dl
                JOIN dentries d ON dl.destinationconversationid = d.conversationid AND dl.destinationdialogueid = d.id
                WHERE dl.originconversationid = ? AND dl.origindialogueid = ?
                AND d.dialoguetext = '0' 
                AND d.conditionstring LIKE ?
            """, (conversation_id, dialogue_id, f"%{check['flagname']}%")).fetchall()
            
            # For each connector, find what follows it
            for connector in connectors:
                final_outcomes = conn.execute("""
                    SELECT dl.destinationconversationid, dl.destinationdialogueid,
                           d.dialoguetext, a.name as actor, d.conditionstring
                    FROM dlinks dl
                    JOIN dentries d ON dl.destinationconversationid = d.conversationid AND dl.destinationdialogueid = d.id
                    JOIN actors a ON d.actor = a.id
                    WHERE dl.originconversationid = ? AND dl.origindialogueid = ?
                    AND d.dialoguetext != '0'
                    AND LENGTH(TRIM(d.dialoguetext)) > 3
                """, (connector['destinationconversationid'], connector['destinationdialogueid'])).fetchall()
                
                for outcome in final_outcomes:
                    # Determine if it's success or failure based on condition
                    is_failure = "== false" in connector['conditionstring'].lower()
                    outcome_type = "FAILURE" if is_failure else "SUCCESS"
                    
                    skill_outcomes.append({
                        'check_flag': check['flagname'],
                        'skilltype': check['skilltype'],
                        'difficulty': check['difficulty'],
                        'outcome_type': outcome_type,
                        'actor': outcome['actor'],
                        'dialogue': outcome['dialoguetext'],
                        'condition': connector['conditionstring'],
                        'conversationid': outcome['destinationconversationid'],
                        'dialogueid': outcome['destinationdialogueid']
                    })
            
            # Method 2: Also search for direct references to the flag in other dialogues
            direct_outcomes = conn.execute("""
                SELECT d.conversationid, d.id as dialogueid, d.dialoguetext, d.conditionstring, a.name as actor
                FROM dentries d
                JOIN actors a ON d.actor = a.id
                WHERE d.conditionstring LIKE ?
                AND d.dialoguetext != '0'
                AND LENGTH(TRIM(d.dialoguetext)) > 3
                AND d.conversationid = ?
                ORDER BY d.id
            """, (f"%{check['flagname']}%", conversation_id)).fetchall()
            
            for outcome in direct_outcomes:
                is_failure = "== false" in outcome['conditionstring'].lower()
                outcome_type = "FAILURE" if is_failure else "SUCCESS"
                
                # Avoid duplicates
                already_exists = any(
                    so['conversationid'] == outcome['conversationid'] and 
                    so['dialogueid'] == outcome['dialogueid']
                    for so in skill_outcomes
                )
                
                if not already_exists:
                    skill_outcomes.append({
                        'check_flag': check['flagname'],
                        'skilltype': check['skilltype'],
                        'difficulty': check['difficulty'],
                        'outcome_type': outcome_type,
                        'actor': outcome['actor'],
                        'dialogue': outcome['dialoguetext'],
                        'condition': outcome['conditionstring'],
                        'conversationid': outcome['conversationid'],
                        'dialogueid': outcome['dialogueid']
                    })
    
    conn.close()
    def format_check(row):
        actual_difficulty, difficulty_label = get_actual_difficulty_and_label(row['difficulty'])
        return {
            'difficulty': row['difficulty'], 
            'actual_difficulty': actual_difficulty,
            'difficulty_label': difficulty_label,
            'skilltype': row['skilltype'], 
            'isred': bool(row['isred']), 
            'flagname': row['flagname']
        }
    
    data = {
        'checks': [format_check(row) for row in checks],
        'alternates': [{'condition': row['condition'], 'alternateline': row['alternateline']} for row in alternates],
        'connected': [{'actor': row['actor'], 'dialogue': row['dialoguetext'], 
                      'hascheck': bool(row['hascheck']), 'isconnector': bool(row['isConnector']),
                      'destinationconversationid': row['destinationconversationid'], 
                      'destinationdialogueid': row['destinationdialogueid'],
                      'condition': row['conditionstring']} for row in links],
        'skill_outcomes': skill_outcomes
    }
    
    return jsonify(data)

@app.route('/search-dialogues', methods=['GET'])
def search_dialogues():
    actor = request.args.get('actor', '').strip()
    keyword = request.args.get('keyword', '')
    conn = get_db_connection()
    
    if not actor:
        # If actor is empty, search across all actors
        query = """
            SELECT actors.name AS actor, actors.id AS actorid, dentries.dialoguetext AS dialogue,
                   dentries.conversationid, dentries.id as dialogueid, dentries.hascheck, dentries.hasalts
            FROM dentries 
            JOIN actors ON dentries.actor = actors.id
            WHERE dentries.dialoguetext LIKE ?
        """
        results = conn.execute(query, (f"%{keyword}%",)).fetchall()
    else:
        # If actor is specified, filter by actor
        query = """
            SELECT actors.name AS actor, actors.id AS actorid, dentries.dialoguetext AS dialogue,
                   dentries.conversationid, dentries.id as dialogueid, dentries.hascheck, dentries.hasalts
            FROM dentries 
            JOIN actors ON dentries.actor = actors.id
            WHERE TRIM(actors.name) = TRIM(?) COLLATE NOCASE 
            AND dentries.dialoguetext LIKE ?
        """
        results = conn.execute(query, (actor, f"%{keyword}%")).fetchall()
    
    conn.close()
    data = [{'actor': row['actor'], 'dialogue': row['dialogue'], 
             'conversationid': row['conversationid'], 'dialogueid': row['dialogueid'],
             'hascheck': bool(row['hascheck']), 'hasalts': bool(row['hasalts'])} for row in results]
    return jsonify(data)

@app.route('/explore-dialogue-tree', methods=['GET'])
def explore_dialogue_tree():
    """
    Enhanced endpoint to explore complete dialogue trees including skill check branches
    """
    conversation_id = request.args.get('conversationid')
    dialogue_id = request.args.get('dialogueid')
    depth = int(request.args.get('depth', 7))  # How many levels deep to explore
    
    if not conversation_id or not dialogue_id:
        return jsonify({'error': 'Missing conversationid or dialogueid'}), 400
    
    conn = get_db_connection()
    
    def get_dialogue_tree(conv_id, dlg_id, current_depth=0, visited=None):
        if visited is None:
            visited = set()
        
        # Prevent infinite loops
        dialogue_key = f"{conv_id}_{dlg_id}"
        if dialogue_key in visited or current_depth >= depth:
            return None
        
        visited.add(dialogue_key)
        
        # Get current dialogue
        current = conn.execute("""
            SELECT d.dialoguetext, a.name as actor, d.hascheck, d.conditionstring
            FROM dentries d
            JOIN actors a ON d.actor = a.id
            WHERE d.conversationid = ? AND d.id = ?
        """, (conv_id, dlg_id)).fetchone()
        
        if not current:
            return None
        
        node = {
            'conversationid': conv_id,
            'dialogueid': dlg_id,
            'actor': current['actor'],
            'dialogue': current['dialoguetext'],
            'hascheck': bool(current['hascheck']),
            'condition': current['conditionstring'],
            'children': [],
            'skill_check': None
        }
        
        # Get skill check if present
        if current['hascheck']:
            check = conn.execute("""
                SELECT difficulty, skilltype, isred, flagname
                FROM checks 
                WHERE conversationid = ? AND dialogueid = ?
            """, (conv_id, dlg_id)).fetchone()
            if check:
                actual_difficulty, difficulty_label = get_actual_difficulty_and_label(check['difficulty'])
                node['skill_check'] = {
                    'difficulty': check['difficulty'],
                    'actual_difficulty': actual_difficulty,
                    'difficulty_label': difficulty_label,
                    'skilltype': check['skilltype'],
                    'isred': bool(check['isred']),
                    'flagname': check['flagname']
                }
        
        # Get all connected dialogues (including system connectors)
        connections = conn.execute("""
            SELECT dl.destinationconversationid, dl.destinationdialogueid, dl.isConnector,
                   d.dialoguetext, d.conditionstring, a.name as actor, dl.priority
            FROM dlinks dl
            JOIN dentries d ON dl.destinationconversationid = d.conversationid AND dl.destinationdialogueid = d.id
            JOIN actors a ON d.actor = a.id
            WHERE dl.originconversationid = ? AND dl.origindialogueid = ?
            ORDER BY dl.priority DESC, dl.destinationdialogueid ASC
        """, (conv_id, dlg_id)).fetchall()
        
        for conn_row in connections:
            # Always process children, even system connectors (dialogue = '0')
            child = get_dialogue_tree(
                conn_row['destinationconversationid'], 
                conn_row['destinationdialogueid'], 
                current_depth + 1, 
                visited.copy()
            )
            
            if child:
                child['is_connector'] = bool(conn_row['isConnector'])
                child['parent_condition'] = conn_row['conditionstring']
                child['priority'] = conn_row['priority']
                node['children'].append(child)
        
        return node
    
    tree = get_dialogue_tree(conversation_id, dialogue_id)
    conn.close()
    
    return jsonify(tree)

if __name__ == '__main__':
    app.run(debug=True)
