# app.py
import os
import uuid
import threading
import resend
from flask import Flask, request, jsonify
from flask_cors import CORS
from config import Config
from database import init_db, get_db
from ml_engine import load_models, classify_issue
from llm_engine import (
    group_issues_into_themes,
    generate_proposal,
    revise_proposal,
    generate_weekly_report,
    generate_safety_advice,
    analyze_image_with_claude,
    is_valid_maintenance_issue
)

# ===== INITIALIZE APP =====
app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH

os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


# ===== HELPER FUNCTIONS =====
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() \
        in Config.ALLOWED_EXTENSIONS


def row_to_dict(row):
    return dict(zip(row.keys(), row))


# ===== EMAIL VIA RESEND =====
def send_email_notification(to_email, subject, body):
    """Send email notification via Resend"""
    try:
        if not Config.RESEND_API_KEY:
            print("⚠️ Resend API key not configured")
            return False

        resend.api_key = Config.RESEND_API_KEY

        html_body = f"""
        <html>
        <body style="font-family:Arial,sans-serif;
            background:#f4f6fb;padding:20px;">
          <div style="max-width:600px;margin:0 auto;
              background:#fff;border-radius:14px;
              overflow:hidden;box-shadow:0 4px 12px
              rgba(0,0,0,0.1);">
            <div style="background:#1a3a6b;padding:24px;
                text-align:center;">
              <h1 style="color:#fff;margin:0;
                  font-size:24px;">ResiFix</h1>
              <p style="color:#aac4e8;margin:6px 0 0;">
                Residence Maintenance System
              </p>
            </div>
            <div style="padding:28px;">
              <h2 style="color:#1a3a6b;margin-top:0;">
                {subject}
              </h2>
              <p style="color:#333;line-height:1.7;
                  white-space:pre-line;">{body}</p>
              <div style="margin-top:24px;padding:16px;
                  background:#f4f6fb;border-radius:8px;
                  border-left:4px solid #2e86de;">
                <p style="margin:0;color:#64748b;
                    font-size:13px;">
                  Please log in to ResiFix to view and
                  respond to this issue immediately.
                </p>
              </div>
            </div>
            <div style="background:#f4f6fb;padding:16px;
                text-align:center;">
              <p style="color:#94a3b8;font-size:12px;margin:0;">
                ResiFix — AI-Powered Residence Maintenance System
              </p>
            </div>
          </div>
        </body>
        </html>
        """

        params = {
            "from": "ResiFix <onboarding@resend.dev>",
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        }

        resend.Emails.send(params)
        print(f"✅ Email sent to {to_email} via Resend")
        return True

    except Exception as e:
        print(f"❌ Resend email error: {e}")
        return False


# ===== BACKGROUND PROPOSAL GENERATION =====
def _generate_proposal_bg(block, issue_type):
    """Generate proposal in background"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM issues
            WHERE block = ? AND issue_type = ?
            AND status = "Open"
            ORDER BY created_at DESC
            LIMIT 20
        ''', (block, issue_type))
        similar_issues = [row_to_dict(r) for r in cursor.fetchall()]
        if not similar_issues:
            conn.close()
            return

        themes_result = group_issues_into_themes(similar_issues)
        if not themes_result['success']:
            conn.close()
            return

        proposal_result = generate_proposal(
            themes_result['themes'], similar_issues, block
        )
        if not proposal_result or not proposal_result['success']:
            conn.close()
            return

        cursor.execute('''
            SELECT id FROM proposals
            WHERE block = ? AND issue_type = ?
            AND status = "Active"
            ORDER BY created_at DESC LIMIT 1
        ''', (block, issue_type))
        existing = cursor.fetchone()

        if existing:
            cursor.execute('''
                UPDATE proposals
                SET description = ?,
                    issues_count = issues_count + 1
                WHERE id = ?
            ''', (proposal_result['proposal'], existing['id']))
        else:
            cursor.execute('''
                INSERT INTO proposals
                (title, description, issue_type, block, issues_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                f"{issue_type} Improvement — {block}",
                proposal_result['proposal'],
                issue_type, block,
                len(similar_issues)
            ))

        conn.commit()
        conn.close()
        print(f"✅ Proposal saved for {block} — {issue_type}")

    except Exception as e:
        print(f"❌ Background proposal error: {e}")


# ===== STARTUP =====
with app.app_context():
    init_db()
    load_models()


# ================================================
# AUTH ROUTES
# ================================================

@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        full_name = data.get('full_name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'student')
        block = data.get('block', '')
        room_number = data.get('room_number', '')

        if not all([full_name, email, password]):
            return jsonify({
                'success': False,
                'message': 'Please fill in all required fields'
            }), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            'SELECT id FROM users WHERE email = ?', (email,)
        )
        if cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Email already registered'
            }), 400

        cursor.execute('''
            INSERT INTO users
            (full_name, email, password, role, block, room_number)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (full_name, email, password, role, block, room_number))

        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'user': {
                'id': user_id,
                'full_name': full_name,
                'email': email,
                'role': role,
                'block': block,
                'room_number': room_number
            }
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/login', methods=['POST'])
def login():
    """Login a user"""
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')

        if not all([email, password]):
            return jsonify({
                'success': False,
                'message': 'Please provide email and password'
            }), 400

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT * FROM users WHERE email = ? AND password = ?',
            (email, password)
        )
        user = cursor.fetchone()
        conn.close()

        if not user:
            return jsonify({
                'success': False,
                'message': 'Invalid email or password'
            }), 401

        user_dict = row_to_dict(user)
        user_dict.pop('password', None)

        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user_dict
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ================================================
# ISSUE ROUTES
# ================================================

@app.route('/api/issues/submit', methods=['POST'])
def submit_issue():
    """Submit a new maintenance issue"""
    try:
        student_id = request.form.get('student_id')
        description = request.form.get('description', '')
        block = request.form.get('block')
        room_number = request.form.get('room_number')
        is_anonymous = request.form.get('is_anonymous', '0')

        if not all([student_id, block, room_number]):
            return jsonify({
                'success': False,
                'message': 'Please fill in all required fields'
            }), 400

        # Handle image upload
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = str(uuid.uuid4()) + '.' + \
                    file.filename.rsplit('.', 1)[1].lower()
                image_path = os.path.join(
                    Config.UPLOAD_FOLDER, filename
                )
                file.save(image_path)

        # ===== VALIDATE TEXT IS A REAL MAINTENANCE ISSUE =====
        # If only text (no image), check it's actually an issue
        if description and not image_path:
            if not is_valid_maintenance_issue(description):
                return jsonify({
                    'success': False,
                    'message': (
                        "I'm not sure that's a maintenance issue. "
                        "Could you please describe the actual "
                        "problem? For example: 'There is a leaking "
                        "tap in my bathroom' or 'The light in my "
                        "room is broken'."
                    )
                }), 400

        # Run ML classification on text first
        ml_result = classify_issue(
            description=description if description else None,
            image_path=None
        )

        # If image uploaded, use Claude Vision
        if image_path:
            vision = analyze_image_with_claude(image_path)
            if vision['success']:
                ml_result['issue_type'] = vision['issue_type']
                ml_result['damage_detected'] = \
                    vision['damage_detected']
                priority_order = ['Critical', 'High',
                                  'Medium', 'Low']
                img_pri = vision['priority']
                txt_pri = ml_result.get('priority', 'Medium')
                if priority_order.index(img_pri) < \
                        priority_order.index(txt_pri):
                    ml_result['priority'] = img_pri
                if not description and vision.get('description'):
                    description = vision['description']

        # Save to database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO issues
            (student_id, description, issue_type, priority,
             block, room_number, image_path,
             image_damage_detected, is_anonymous)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            student_id, description,
            ml_result['issue_type'],
            ml_result['priority'],
            block, room_number, image_path,
            1 if ml_result.get('damage_detected') else 0,
            int(is_anonymous)
        ))

        conn.commit()
        issue_id = cursor.lastrowid

        # Generate safety advice
        safety_result = generate_safety_advice(
            ml_result['issue_type'],
            ml_result['priority'],
            description
        )

        # Notify matron
        cursor.execute('''
            SELECT id, email, full_name FROM users
            WHERE role = "matron" AND block = ?
        ''', (block,))
        matron = cursor.fetchone()

        if matron:
            matron_dict = row_to_dict(matron)
            message = (
                f"🚨 New {ml_result['priority']} priority "
                f"{ml_result['issue_type']} issue submitted "
                f"in {block} Room {room_number}"
            )
            cursor.execute('''
                INSERT INTO notifications (user_id, message)
                VALUES (?, ?)
            ''', (matron_dict['id'], message))
            conn.commit()

            if ml_result['priority'] in \
                    Config.EMAIL_ALERT_PRIORITIES:
                email_subject = (
                    f"🚨 ResiFix Alert — "
                    f"{ml_result['priority']} Priority "
                    f"{ml_result['issue_type']} Issue in {block}"
                )
                email_body = (
                    f"Dear {matron_dict['full_name']},\n\n"
                    f"A {ml_result['priority']} priority "
                    f"maintenance issue has been reported in "
                    f"your block.\n\n"
                    f"ISSUE DETAILS:\n"
                    f"Block: {block}\n"
                    f"Room: {room_number}\n"
                    f"Type: {ml_result['issue_type']}\n"
                    f"Priority: {ml_result['priority']}\n"
                    f"Description: {description}\n\n"
                    f"Expected Response Time: "
                    f"{safety_result.get('expected_time', 'ASAP')}"
                    f"\n\nPlease log in to ResiFix immediately."
                )
                send_email_notification(
                    matron_dict['email'],
                    email_subject,
                    email_body
                )

        # Notify all admins for Critical
        if ml_result['priority'] == 'Critical':
            cursor.execute('''
                SELECT id, email, full_name FROM users
                WHERE role = "admin"
            ''')
            admins = [
                row_to_dict(row) for row in cursor.fetchall()
            ]
            for admin in admins:
                cursor.execute('''
                    INSERT INTO notifications (user_id, message)
                    VALUES (?, ?)
                ''', (
                    admin['id'],
                    f"🔴 CRITICAL issue in {block} Room "
                    f"{room_number} — {ml_result['issue_type']}"
                ))
                email_subject = (
                    f"🔴 CRITICAL ResiFix Alert — "
                    f"{ml_result['issue_type']} in {block}"
                )
                email_body = (
                    f"Dear {admin['full_name']},\n\n"
                    f"A CRITICAL maintenance issue requires "
                    f"immediate attention.\n\n"
                    f"ISSUE DETAILS:\n"
                    f"Block: {block}\n"
                    f"Room: {room_number}\n"
                    f"Type: {ml_result['issue_type']}\n"
                    f"Priority: CRITICAL\n"
                    f"Description: {description}\n\n"
                    f"Please ensure the matron responds within "
                    f"10 to 20 minutes."
                )
                send_email_notification(
                    admin['email'],
                    email_subject,
                    email_body
                )
            conn.commit()

        conn.close()

        # Generate proposal in background
        threading.Thread(
            target=_generate_proposal_bg,
            args=(block, ml_result['issue_type']),
            daemon=True
        ).start()

        return jsonify({
            'success': True,
            'message': 'Issue submitted successfully',
            'issue': {
                'id': issue_id,
                'issue_type': ml_result['issue_type'],
                'priority': ml_result['priority'],
                'damage_detected': ml_result.get(
                    'damage_detected', False
                ),
                'status': 'Open'
            },
            'safety_advice': safety_result.get('advice', ''),
            'expected_time': safety_result.get('expected_time', ''),
            'proposal_generated': True
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/issues', methods=['GET'])
def get_issues():
    """Get all issues filtered by role"""
    try:
        role = request.args.get('role', 'student')
        user_id = request.args.get('user_id')
        block = request.args.get('block')

        conn = get_db()
        cursor = conn.cursor()

        if role == 'student':
            cursor.execute('''
                SELECT * FROM issues
                WHERE student_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))

        elif role == 'matron':
            cursor.execute('''
                SELECT * FROM issues
                WHERE block = ?
                ORDER BY
                CASE priority
                    WHEN "Critical" THEN 1
                    WHEN "High" THEN 2
                    WHEN "Medium" THEN 3
                    WHEN "Low" THEN 4
                END,
                created_at DESC
            ''', (block,))

        else:
            cursor.execute('''
                SELECT * FROM issues
                ORDER BY
                CASE priority
                    WHEN "Critical" THEN 1
                    WHEN "High" THEN 2
                    WHEN "Medium" THEN 3
                    WHEN "Low" THEN 4
                END,
                created_at DESC
            ''')

        issues = [row_to_dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            'success': True,
            'issues': issues,
            'total': len(issues)
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/issues/<int:issue_id>/status', methods=['PUT'])
def update_issue_status(issue_id):
    """Update issue status"""
    try:
        data = request.get_json()
        new_status = data.get('status')

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE issues SET status = ?
            WHERE id = ?
        ''', (new_status, issue_id))

        cursor.execute(
            'SELECT student_id FROM issues WHERE id = ?',
            (issue_id,)
        )
        issue = cursor.fetchone()
        if issue:
            cursor.execute('''
                INSERT INTO notifications (user_id, message)
                VALUES (?, ?)
            ''', (
                issue['student_id'],
                f"✅ Your issue #{issue_id} has been updated "
                f"to: {new_status}"
            ))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Issue status updated to {new_status}'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ================================================
# PROPOSAL ROUTES
# ================================================

@app.route('/api/proposals/generate', methods=['POST'])
def generate_proposals():
    """Generate LLM proposals from grouped issues"""
    try:
        data = request.get_json()
        block = data.get('block')

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM issues
            WHERE block = ? AND status = "Open"
            ORDER BY created_at DESC
            LIMIT 50
        ''', (block,))

        issues = [row_to_dict(row) for row in cursor.fetchall()]

        if not issues:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'No open issues found for this block'
            }), 404

        themes_result = group_issues_into_themes(issues)

        if not themes_result['success']:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Failed to group issues'
            }), 500

        proposal_result = generate_proposal(
            themes_result['themes'], issues, block
        )

        if not proposal_result['success']:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Failed to generate proposal'
            }), 500

        cursor.execute('''
            INSERT INTO proposals
            (title, description, issue_type, block, issues_count)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            f"Improvement Proposal for {block}",
            proposal_result['proposal'],
            issues[0]['issue_type'],
            block,
            len(issues)
        ))

        conn.commit()
        proposal_id = cursor.lastrowid
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Proposal generated successfully',
            'proposal_id': proposal_id,
            'themes': themes_result['themes'],
            'proposal': proposal_result['proposal']
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/proposals', methods=['GET'])
def get_proposals():
    """Get all proposals sorted by vote count"""
    try:
        block = request.args.get('block')
        conn = get_db()
        cursor = conn.cursor()

        if block:
            cursor.execute('''
                SELECT p.*,
                COUNT(CASE WHEN v.vote_type = "upvote"
                    THEN 1 END) as upvotes,
                COUNT(CASE WHEN v.vote_type = "downvote"
                    THEN 1 END) as downvotes
                FROM proposals p
                LEFT JOIN votes v ON p.id = v.proposal_id
                WHERE p.block = ?
                GROUP BY p.id
                ORDER BY upvotes DESC, p.created_at DESC
            ''', (block,))
        else:
            cursor.execute('''
                SELECT p.*,
                COUNT(CASE WHEN v.vote_type = "upvote"
                    THEN 1 END) as upvotes,
                COUNT(CASE WHEN v.vote_type = "downvote"
                    THEN 1 END) as downvotes
                FROM proposals p
                LEFT JOIN votes v ON p.id = v.proposal_id
                GROUP BY p.id
                ORDER BY upvotes DESC, p.created_at DESC
            ''')

        proposals = [row_to_dict(row) for row in cursor.fetchall()]
        conn.close()

        return jsonify({
            'success': True,
            'proposals': proposals
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/proposals/<int:proposal_id>/vote',
           methods=['POST'])
def vote_on_proposal(proposal_id):
    """Student votes on a proposal"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        vote_type = data.get('vote_type')
        comment = data.get('comment', '')

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id FROM votes
            WHERE proposal_id = ? AND student_id = ?
        ''', (proposal_id, student_id))

        if cursor.fetchone():
            conn.close()
            return jsonify({
                'success': False,
                'message': 'You have already voted'
            }), 400

        cursor.execute('''
            INSERT INTO votes
            (proposal_id, student_id, vote_type, comment)
            VALUES (?, ?, ?, ?)
        ''', (proposal_id, student_id, vote_type, comment))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Vote submitted successfully'
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/proposals/<int:proposal_id>/revise',
           methods=['POST'])
def revise_proposal_route(proposal_id):
    """Revise proposal based on student votes"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            'SELECT * FROM proposals WHERE id = ?',
            (proposal_id,)
        )
        proposal = row_to_dict(cursor.fetchone())

        cursor.execute('''
            SELECT vote_type, comment FROM votes
            WHERE proposal_id = ?
        ''', (proposal_id,))
        votes = [row_to_dict(row) for row in cursor.fetchall()]
        comments = [v['comment'] for v in votes if v['comment']]

        revised = revise_proposal(
            proposal['description'], votes, comments
        )

        if not revised['success']:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Failed to revise proposal'
            }), 500

        cursor.execute('''
            UPDATE proposals
            SET description = ?
            WHERE id = ?
        ''', (revised['revised_proposal'], proposal_id))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Proposal revised successfully',
            'revised_proposal': revised['revised_proposal']
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ================================================
# NOTIFICATION ROUTES
# ================================================

@app.route('/api/notifications/<int:user_id>', methods=['GET'])
def get_notifications(user_id):
    """Get notifications for a user"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (user_id,))

        notifications = [
            row_to_dict(row) for row in cursor.fetchall()
        ]
        unread = sum(
            1 for n in notifications if n['is_read'] == 0
        )
        conn.close()

        return jsonify({
            'success': True,
            'notifications': notifications,
            'unread_count': unread
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ================================================
# REPORT ROUTES
# ================================================

@app.route('/api/reports/weekly', methods=['GET'])
def get_weekly_report():
    """Generate weekly report for management"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM issues')
        issues = [row_to_dict(row) for row in cursor.fetchall()]

        cursor.execute('SELECT * FROM proposals')
        proposals = [
            row_to_dict(row) for row in cursor.fetchall()
        ]

        cursor.execute('SELECT * FROM votes')
        votes = [row_to_dict(row) for row in cursor.fetchall()]

        conn.close()

        report = generate_weekly_report(issues, proposals, votes)

        return jsonify({
            'success': True,
            'report': report['report']
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ================================================
# PROPOSAL STATUS UPDATE
# ================================================

@app.route('/api/proposals/<int:proposal_id>/status',
           methods=['PUT'])
def update_proposal_status(proposal_id):
    """Admin approves or rejects a proposal"""
    try:
        data = request.get_json()
        new_status = data.get('status')

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE proposals SET status = ?
            WHERE id = ?
        ''', (new_status, proposal_id))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Proposal {new_status.lower()}'
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ================================================
# RATINGS ROUTES
# ================================================

@app.route('/api/ratings', methods=['POST'])
def submit_rating():
    """Student submits a system usability rating"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        overall_rating = data.get('overall_rating')
        ease_of_reporting = data.get('ease_of_reporting', 0)
        ai_helpfulness = data.get('ai_helpfulness', 0)
        response_satisfaction = data.get(
            'response_satisfaction', 0
        )
        safety_advice_clarity = data.get(
            'safety_advice_clarity', 0
        )
        comment = data.get('comment', '')

        if not student_id or not overall_rating:
            return jsonify({
                'success': False,
                'message': 'Please provide a rating'
            }), 400

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO ratings
            (student_id, overall_rating, ease_of_reporting,
             ai_helpfulness, response_satisfaction,
             safety_advice_clarity, comment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            student_id, overall_rating, ease_of_reporting,
            ai_helpfulness, response_satisfaction,
            safety_advice_clarity, comment
        ))

        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Rating submitted successfully'
        }), 201

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/ratings', methods=['GET'])
def get_ratings():
    """Get all ratings with summary stats"""
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM ratings
            ORDER BY created_at DESC
        ''')
        ratings = [row_to_dict(row) for row in cursor.fetchall()]
        conn.close()

        if not ratings:
            return jsonify({
                'success': True,
                'ratings': [],
                'summary': {
                    'total': 0,
                    'avg_overall': 0,
                    'avg_ease': 0,
                    'avg_ai': 0,
                    'avg_response': 0,
                    'avg_safety': 0
                }
            }), 200

        total = len(ratings)
        summary = {
            'total': total,
            'avg_overall': sum(
                r['overall_rating'] for r in ratings
            ) / total,
            'avg_ease': sum(
                r['ease_of_reporting'] for r in ratings
            ) / total,
            'avg_ai': sum(
                r['ai_helpfulness'] for r in ratings
            ) / total,
            'avg_response': sum(
                r['response_satisfaction'] for r in ratings
            ) / total,
            'avg_safety': sum(
                r['safety_advice_clarity'] for r in ratings
            ) / total
        }

        return jsonify({
            'success': True,
            'ratings': ratings,
            'summary': summary
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# ================================================
# RUN APP
# ================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)