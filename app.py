import os
import psycopg2
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Get database URL from environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Fix for Render's connection string
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def get_db_connection():
    """Create and return a PostgreSQL database connection"""
    try:
        if DATABASE_URL:
            # Use connection string for Render
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        else:
            # Local development
            conn = psycopg2.connect(
                host=os.environ.get('DB_HOST', 'localhost'),
                database=os.environ.get('DB_NAME', 'study'),
                user=os.environ.get('DB_USER', 'postgres'),
                password=os.environ.get('DB_PASSWORD', '@jk3'),
                port=os.environ.get('DB_PORT', '5432')
            )
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None


def init_db():
    """Initialize the database with students table"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    student_id VARCHAR(20) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    phone VARCHAR(20),
                    course VARCHAR(100),
                    year INTEGER,
                    address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            cur.close()
            conn.close()
            print("Database initialized successfully")
        except Exception as e:
            print(f"Error initializing database: {e}")


# Initialize database when app starts
init_db()


@app.route('/')
def index():
    """Render the main HTML page"""
    return render_template('index.html')


# API Endpoints (keep all your endpoints - they're fine)
@app.route('/api/students', methods=['GET'])
def get_students():
    """Get all students"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM students ORDER BY id DESC')
        students = cur.fetchall()

        # Convert to list of dictionaries
        student_list = []
        for student in students:
            student_list.append({
                'id': student[0],
                'student_id': student[1],
                'name': student[2],
                'email': student[3],
                'phone': student[4],
                'course': student[5],
                'year': student[6],
                'address': student[7],
                'created_at': student[8].strftime('%Y-%m-%d %H:%M:%S') if student[8] else None
            })

        cur.close()
        conn.close()
        return jsonify(student_list)
    except Exception as e:
        print(f"Error fetching students: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/students', methods=['POST'])
def add_student():
    """Add a new student"""
    data = request.json
    required_fields = ['student_id', 'name', 'email']

    # Validate required fields
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO students (student_id, name, email, phone, course, year, address)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (
            data['student_id'],
            data['name'],
            data['email'],
            data.get('phone', ''),
            data.get('course', ''),
            data.get('year'),
            data.get('address', '')
        ))

        student_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'message': 'Student added successfully',
            'id': student_id
        }), 201
    except psycopg2.IntegrityError as e:
        conn.rollback()
        return jsonify({'error': 'Student ID or Email already exists'}), 400
    except Exception as e:
        conn.rollback()
        print(f"Error adding student: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/students/<int:id>', methods=['PUT'])
def update_student(id):
    """Update student details"""
    data = request.json

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE students 
            SET student_id = %s, name = %s, email = %s, phone = %s, 
                course = %s, year = %s, address = %s
            WHERE id = %s
        ''', (
            data.get('student_id'),
            data.get('name'),
            data.get('email'),
            data.get('phone', ''),
            data.get('course', ''),
            data.get('year'),
            data.get('address', ''),
            id
        ))

        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({'error': 'Student not found'}), 404

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'message': 'Student updated successfully'})
    except psycopg2.IntegrityError as e:
        conn.rollback()
        return jsonify({'error': 'Student ID or Email already exists'}), 400
    except Exception as e:
        conn.rollback()
        print(f"Error updating student: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/students/<int:id>', methods=['DELETE'])
def delete_student(id):
    """Delete a student"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM students WHERE id = %s', (id,))

        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({'error': 'Student not found'}), 404

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({'message': 'Student deleted successfully'})
    except Exception as e:
        conn.rollback()
        print(f"Error deleting student: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/students/search', methods=['GET'])
def search_students():
    """Search students by name or student ID"""
    query = request.args.get('query', '')

    if not query:
        return jsonify([])

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT * FROM students 
            WHERE name ILIKE %s OR student_id ILIKE %s 
            ORDER BY id DESC
        ''', (f'%{query}%', f'%{query}%'))

        students = cur.fetchall()
        student_list = []
        for student in students:
            student_list.append({
                'id': student[0],
                'student_id': student[1],
                'name': student[2],
                'email': student[3],
                'phone': student[4],
                'course': student[5],
                'year': student[6],
                'address': student[7],
                'created_at': student[8].strftime('%Y-%m-%d %H:%M:%S') if student[8] else None
            })

        cur.close()
        conn.close()
        return jsonify(student_list)
    except Exception as e:
        print(f"Error searching students: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)