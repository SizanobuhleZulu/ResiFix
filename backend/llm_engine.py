# llm_engine.py
import anthropic
import base64
from config import Config

# Initialize Claude client
client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)


# ===== VALIDATE IF TEXT IS A REAL MAINTENANCE ISSUE =====
def is_valid_maintenance_issue(description):
    """
    Check if the text actually describes a maintenance issue.
    Returns True if real issue, False if greeting/gibberish.
    """
    try:
        text = description.strip().lower()

        # Too short to be a real issue
        if len(text) < 10:
            return False

        # Common greetings and non-issues
        greetings = [
            'hi', 'hello', 'hey', 'sup', 'yo', 'hola',
            'good morning', 'good afternoon', 'good evening',
            'how are you', 'whats up', "what's up",
            'test', 'testing', 'asdf', 'qwer', 'zxcv'
        ]
        if text in greetings or len(text.split()) < 3:
            return False

        # Use Claude for ambiguous cases
        prompt = f"""
You are a strict validator for a university residence
maintenance reporting system. Decide if the following text
is describing a REAL maintenance issue in a residence room
or building.

TEXT: "{description}"

A REAL maintenance issue describes a physical problem with:
- Electrical things (wires, plugs, lights, switches)
- Plumbing (taps, pipes, drains, toilets, showers)
- Structural things (walls, doors, windows, ceilings)
- Hygiene/safety (mould, pests, dirt, ventilation)
- Administrative things (room access, missing items)

NOT a maintenance issue:
- Greetings (hi, hello)
- General questions about the system
- Random text or gibberish
- Personal complaints unrelated to the room
- Test inputs

Respond with ONLY one word: VALID or INVALID
"""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text.strip().upper()
        return "VALID" in result

    except Exception as e:
        print(f"❌ Validator error: {e}")
        return True


# ===== ANALYZE IMAGE WITH CLAUDE VISION =====
def analyze_image_with_claude(image_path):
    """Use Claude Vision to analyze a photo of damage"""
    try:
        with open(image_path, 'rb') as image_file:
            image_data = base64.standard_b64encode(
                image_file.read()
            ).decode('utf-8')

        ext = image_path.lower().split('.')[-1]
        media_type = 'image/jpeg' if ext in ['jpg', 'jpeg'] \
            else f'image/{ext}'

        prompt = """
You are an expert residence maintenance inspector.
Analyze this photo and determine:

1. ISSUE TYPE — Choose ONE: Electrical, Plumbing,
   Structural, Hygiene & Safety, Administrative

2. PRIORITY — Choose ONE: Critical, High, Medium, Low

3. DAMAGE DETECTED — true or false

4. DESCRIPTION — Short factual description (10-20 words)

Respond ONLY in this format:
ISSUE_TYPE: [type]
PRIORITY: [priority]
DAMAGE_DETECTED: [true or false]
DESCRIPTION: [your description]
"""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ]
        )

        text = response.content[0].text.strip()
        result = {
            'issue_type': 'Administrative',
            'priority': 'Medium',
            'damage_detected': False,
            'description': '',
            'success': True
        }

        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('ISSUE_TYPE:'):
                value = line.replace('ISSUE_TYPE:', '').strip()
                valid_types = ['Electrical', 'Plumbing',
                               'Structural', 'Hygiene & Safety',
                               'Administrative']
                for vt in valid_types:
                    if vt.lower() in value.lower():
                        result['issue_type'] = vt
                        break
            elif line.startswith('PRIORITY:'):
                value = line.replace('PRIORITY:', '').strip()
                for vp in ['Critical', 'High', 'Medium', 'Low']:
                    if vp.lower() in value.lower():
                        result['priority'] = vp
                        break
            elif line.startswith('DAMAGE_DETECTED:'):
                value = line.replace(
                    'DAMAGE_DETECTED:', ''
                ).strip().lower()
                result['damage_detected'] = 'true' in value
            elif line.startswith('DESCRIPTION:'):
                result['description'] = line.replace(
                    'DESCRIPTION:', ''
                ).strip()

        print(f"📸 Image: {result['issue_type']} - "
              f"{result['priority']} - "
              f"Damage: {result['damage_detected']}")

        return result

    except Exception as e:
        print(f"❌ Image analysis error: {e}")
        return {
            'issue_type': 'Administrative',
            'priority': 'Medium',
            'damage_detected': False,
            'description': '',
            'success': False
        }


# ===== GENERATE SAFETY ADVICE =====
def generate_safety_advice(issue_type, priority, description):
    """Claude gives safety advice and expected response time"""
    try:
        response_times = {
            'Critical': '10 to 20 minutes',
            'High': '1 to 2 hours',
            'Medium': '24 hours',
            'Low': '2 to 3 days'
        }
        expected_time = response_times.get(priority, '24 hours')

        prompt = f"""
You are a caring residence maintenance assistant.
A student reported an issue.

ISSUE: {issue_type} ({priority} priority)
DESCRIPTION: {description}
EXPECTED TIME: {expected_time}

Give the student:
1. Reassurance that help is coming
2. The expected response time
3. Specific safety advice for this issue type
4. A warm, caring tone

For ELECTRICAL: warn about wires, suggest leaving room
For PLUMBING: bucket for leaks, turn off water if safe
For STRUCTURAL: stay away from damaged areas
For HYGIENE: ventilation, avoid bare hands
For ADMINISTRATIVE: confirm right person notified

If CRITICAL, urgently reassure help is coming immediately.

Write 3-5 sentences, conversational, no bullet points.
"""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'success': True,
            'advice': response.content[0].text,
            'expected_time': expected_time
        }

    except Exception as e:
        print(f"❌ Safety advice error: {e}")
        fallback = {
            'Electrical': (
                'Please do not touch any wires. If unsafe, '
                'leave the room and wait until help arrives.'
            ),
            'Plumbing': (
                'Place a bucket under the leak. Turn off '
                'the tap if you can reach it safely.'
            ),
            'Structural': (
                'Stay away from the damaged area. Do not '
                'lean on cracked walls or ceilings.'
            ),
            'Hygiene & Safety': (
                'Keep windows open for ventilation. Avoid '
                'touching affected areas with bare hands.'
            ),
            'Administrative': (
                'Your request has been received. The right '
                'person has been notified.'
            )
        }
        return {
            'success': True,
            'advice': fallback.get(
                issue_type,
                'Your issue has been received. Help is coming!'
            ),
            'expected_time': response_times.get(priority, '24 hours')
        }


# ===== GROUP ISSUES INTO THEMES =====
def group_issues_into_themes(issues):
    """Group issues into common themes"""
    try:
        issues_text = ""
        for i, issue in enumerate(issues, 1):
            issues_text += f"""
Issue {i}:
- Description: {issue['description']}
- Type: {issue['issue_type']}
- Priority: {issue['priority']}
- Block: {issue['block']}
- Room: {issue['room_number']}
"""

        prompt = f"""
Analyze these maintenance issues and group into themes:
{issues_text}

Format:
THEME 1: [Name]
AFFECTED BLOCKS: [List]
ISSUE COUNT: [Number]
URGENCY: [Critical/High/Medium/Low]
SUMMARY: [2-3 sentences]
---
"""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'success': True,
            'themes': response.content[0].text
        }

    except Exception as e:
        print(f"❌ Theme grouping error: {e}")
        return {'success': False, 'themes': ''}


# ===== GENERATE PROPOSAL =====
def generate_proposal(theme, issues, block):
    """Generate improvement proposal"""
    try:
        issues_text = ""
        for issue in issues:
            issues_text += (
                f"- {issue['description']} "
                f"(Priority: {issue['priority']})\n"
            )

        prompt = f"""
Generate a residence improvement proposal:

THEME: {theme}
BLOCK: {block}
ISSUES:
{issues_text}

Include:
1. Title
2. Problem summary
3. Proposed solution
4. Resources needed (materials, budget)
5. Expected outcome
6. Timeline
7. Success metrics

Keep practical and affordable.
"""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'success': True,
            'proposal': response.content[0].text
        }

    except Exception as e:
        print(f"❌ Proposal error: {e}")
        return {'success': False, 'proposal': ''}


# ===== REVISE PROPOSAL =====
def revise_proposal(original_proposal, votes, comments):
    """Revise proposal based on student feedback"""
    try:
        upvotes = sum(
            1 for v in votes if v['vote_type'] == 'upvote'
        )
        downvotes = sum(
            1 for v in votes if v['vote_type'] == 'downvote'
        )

        comments_text = ""
        for comment in comments:
            if comment:
                comments_text += f"- {comment}\n"

        prompt = f"""
Revise this proposal based on student feedback:

ORIGINAL:
{original_proposal}

FEEDBACK:
- Upvotes: {upvotes}
- Downvotes: {downvotes}
- Comments:
{comments_text if comments_text else "None"}

Generate an improved version addressing concerns.
"""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'success': True,
            'revised_proposal': response.content[0].text
        }

    except Exception as e:
        print(f"❌ Revise proposal error: {e}")
        return {'success': False, 'revised_proposal': ''}


# ===== GENERATE WEEKLY REPORT =====
def generate_weekly_report(issues, proposals, votes):
    """Generate weekly management report"""
    try:
        total_issues = len(issues)
        critical_issues = sum(
            1 for i in issues if i['priority'] == 'Critical'
        )
        resolved_issues = sum(
            1 for i in issues if i['status'] == 'Resolved'
        )
        total_proposals = len(proposals)
        total_votes = len(votes)

        type_counts = {}
        for issue in issues:
            t = issue['issue_type']
            type_counts[t] = type_counts.get(t, 0) + 1

        block_counts = {}
        for issue in issues:
            b = issue['block']
            block_counts[b] = block_counts.get(b, 0) + 1

        prompt = f"""
Generate weekly residence maintenance report:

STATS:
- Total Issues: {total_issues}
- Critical: {critical_issues}
- Resolved: {resolved_issues}
- Proposals: {total_proposals}
- Votes: {total_votes}

BY TYPE: {type_counts}
BY BLOCK: {block_counts}

Include:
1. Executive summary
2. Key highlights
3. Block breakdown
4. Common issue types
5. Pending proposals
6. Recommended actions
7. Outlook
"""

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        return {
            'success': True,
            'report': response.content[0].text
        }

    except Exception as e:
        print(f"❌ Report error: {e}")
        return {'success': False, 'report': ''}