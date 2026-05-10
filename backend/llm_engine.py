# llm_engine.py
import anthropic
import base64
from config import Config

# Initialize Claude client
client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)


# ===== ANALYZE IMAGE WITH CLAUDE VISION =====
def analyze_image_with_claude(image_path):
    """
    Use Claude Vision to analyze a photo of damage
    and return the issue type, priority, and description
    """
    try:
        # Read image and convert to base64
        with open(image_path, 'rb') as image_file:
            image_data = base64.standard_b64encode(
                image_file.read()
            ).decode('utf-8')

        # Determine image type
        ext = image_path.lower().split('.')[-1]
        media_type = 'image/jpeg' if ext in ['jpg', 'jpeg'] \
            else f'image/{ext}'

        prompt = """
You are an expert residence maintenance inspector at a 
university campus. A student has uploaded a photo of a 
maintenance issue in their residence room.

Please analyze this photo and determine:

1. ISSUE TYPE — Choose ONE from:
   - Electrical (exposed wires, broken plug, burnt sockets, 
     flickering lights, electrical sparks)
   - Plumbing (water leaks, burst pipes, blocked drains, 
     overflowing toilets, broken taps)
   - Structural (cracked walls, broken doors, damaged 
     windows, sagging ceilings, broken furniture)
   - Hygiene & Safety (mould, pest infestation, dirt, 
     unsanitary conditions, blocked vents)
   - Administrative (other damage that needs documentation 
     but no immediate physical hazard)

2. PRIORITY — Choose ONE based on severity:
   - Critical (immediate danger to life or property — 
     fires, exposed live wires, major flooding, gas leaks, 
     structural collapse risk)
   - High (significant damage that needs urgent attention 
     within hours — major leaks, broken security features, 
     widespread mould)
   - Medium (notable issue that should be fixed within 
     a day — small leaks, minor cracks, broken fixtures)
   - Low (cosmetic or minor issues — small marks, 
     loose handles, small dirt patches)

3. DAMAGE DETECTED — true if you can see clear damage 
   or unsafe conditions in the photo, false otherwise

4. DESCRIPTION — A short factual sentence describing 
   what you see in 10-20 words

Respond ONLY in this exact format with no extra text:

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
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        # Parse the response
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
                # Validate it's one of our categories
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

        print(f"📸 Image analysis: {result['issue_type']} — "
              f"{result['priority']} — "
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
    """
    After issue is classified, Claude gives the student
    specific safety advice and expected response time
    """
    try:
        response_times = {
            'Critical': '10 to 20 minutes',
            'High': '1 to 2 hours',
            'Medium': '24 hours',
            'Low': '2 to 3 days'
        }
        expected_time = response_times.get(priority, '24 hours')

        prompt = f"""
You are a helpful and caring residence maintenance assistant 
at a university campus. A student has just reported a 
maintenance issue and it has been automatically classified 
and submitted to the maintenance team.

ISSUE DETAILS:
- Issue Type: {issue_type}
- Priority Level: {priority}
- Student Description: {description}
- Expected Response Time: {expected_time}

Your job is to:
1. Reassure the student their issue has been received
2. Tell them the expected response time based on priority
3. Give them clear, practical safety advice specific to 
   their issue type while they wait for help
4. Keep your tone warm, caring, and reassuring

SAFETY ADVICE RULES:
- If ELECTRICAL issue: Warn about dangers, advise not to 
  touch wires, suggest leaving the room if dangerous,
  unplug devices, do not use switches
- If PLUMBING issue: Advise to get a bucket for leaks,
  turn off water tap if possible, protect belongings 
  from water damage, avoid slipping on wet floors
- If STRUCTURAL issue: Advise to stay away from the 
  damaged area, do not lean on cracked walls or ceilings,
  move belongings away from danger zone
- If HYGIENE & SAFETY issue: Advise to keep windows open
  for ventilation, avoid touching mould with bare hands,
  keep food away from pest-affected areas
- If ADMINISTRATIVE issue: Reassure them the right person 
  has been notified and will contact them soon

If priority is CRITICAL, start your response with an 
urgent reassurance that help is on the way immediately.

Keep your response concise, friendly, and practical.
Write in 3 to 5 sentences maximum.
Do NOT use bullet points — write in natural conversational 
sentences as if speaking directly to the student.
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
        print(f"❌ Error generating safety advice: {e}")
        fallback = {
            'Electrical': (
                'Please do not touch any wires or electrical '
                'fittings. If you feel unsafe please leave the '
                'room and wait outside until help arrives.'
            ),
            'Plumbing': (
                'Please place a bucket or towel under the leak '
                'to minimise water damage. Turn off the tap if '
                'you can reach it safely.'
            ),
            'Structural': (
                'Please stay away from the damaged area and do '
                'not lean on cracked walls or ceilings. Move '
                'your belongings away from the danger zone.'
            ),
            'Hygiene & Safety': (
                'Please keep your windows open for ventilation '
                'and avoid touching affected areas with bare '
                'hands until the team arrives.'
            ),
            'Administrative': (
                'Your request has been received and the right '
                'person has been notified. They will contact '
                'you shortly.'
            )
        }
        return {
            'success': True,
            'advice': fallback.get(
                issue_type,
                'Your issue has been received. Help is on the way!'
            ),
            'expected_time': response_times.get(priority, '24 hours')
        }


# ===== GROUP ISSUES INTO THEMES =====
def group_issues_into_themes(issues):
    """
    Takes a list of issues and uses Claude
    to group them into common themes
    """
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
You are an AI assistant helping to analyze residence 
maintenance issues at a university campus.

Here are the recent maintenance issues submitted by students:
{issues_text}

Please analyze these issues and:
1. Group them into common themes
2. Identify which blocks are most affected
3. Identify the most urgent patterns
4. Count how many issues fall into each theme

Respond in this exact format:
THEME 1: [Theme Name]
AFFECTED BLOCKS: [List of blocks]
ISSUE COUNT: [Number]
URGENCY: [Critical/High/Medium/Low]
SUMMARY: [2-3 sentence description of the theme]
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
        print(f"❌ Error grouping issues: {e}")
        return {'success': False, 'themes': ''}


# ===== GENERATE IMPROVEMENT PROPOSALS =====
def generate_proposal(theme, issues, block):
    """
    Takes a theme and generates a detailed
    improvement proposal for residence management
    """
    try:
        issues_text = ""
        for issue in issues:
            issues_text += (
                f"- {issue['description']} "
                f"(Priority: {issue['priority']})\n"
            )

        prompt = f"""
You are an AI co-designer helping improve student residence
conditions at a university campus.

THEME: {theme}
AFFECTED BLOCK: {block}
STUDENT ISSUES:
{issues_text}

Based on these recurring student issues please generate a
detailed residence improvement proposal that includes:

1. A clear title for the proposal
2. Problem summary - what is going wrong
3. Proposed solution - practical steps to fix it
4. Resources needed - materials, staff, budget estimate
5. Expected outcome - how students will benefit
6. Implementation timeline - realistic timeframe
7. Success metrics - how we measure if it worked

Make the proposal practical, affordable, and focused on
improving student wellbeing.
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
        print(f"❌ Error generating proposal: {e}")
        return {'success': False, 'proposal': ''}


# ===== REVISE PROPOSAL BASED ON FEEDBACK =====
def revise_proposal(original_proposal, votes, comments):
    """
    Takes student votes and comments and
    revises the proposal accordingly
    """
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
You are an AI co-designer helping improve a residence
improvement proposal based on student feedback.

ORIGINAL PROPOSAL:
{original_proposal}

STUDENT FEEDBACK:
- Upvotes: {upvotes}
- Downvotes: {downvotes}
- Student Comments:
{comments_text if comments_text else "No comments provided"}

Generate an improved version of the proposal that better
reflects student needs and concerns.
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
        print(f"❌ Error revising proposal: {e}")
        return {'success': False, 'revised_proposal': ''}


# ===== GENERATE WEEKLY REPORT =====
def generate_weekly_report(issues, proposals, votes):
    """
    Generates a weekly summary report
    for residence management
    """
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
You are an AI assistant generating a weekly residence
maintenance report for university management.

WEEKLY STATISTICS:
- Total Issues Submitted: {total_issues}
- Critical Issues: {critical_issues}
- Resolved Issues: {resolved_issues}
- Improvement Proposals Generated: {total_proposals}
- Student Votes on Proposals: {total_votes}

ISSUES BY TYPE:
{type_counts}

ISSUES BY BLOCK:
{block_counts}

Please generate a professional weekly report that includes:
1. Executive summary
2. Key highlights and urgent matters
3. Block by block breakdown
4. Most common issue types
5. Proposals awaiting approval
6. Recommended immediate actions
7. Outlook for next week
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
        print(f"❌ Error generating report: {e}")
        return {'success': False, 'report': ''}