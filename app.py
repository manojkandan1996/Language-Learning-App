from flask import Flask, render_template, redirect, url_for, request, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from gtts import gTTS
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'devkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///language.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---

class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    meaning = db.Column(db.String(200), nullable=False)
    next_review = db.Column(db.DateTime, default=datetime.utcnow)
    interval = db.Column(db.Integer, default=1)  # days
    repetitions = db.Column(db.Integer, default=0)
    easiness = db.Column(db.Float, default=2.5)  # SM-2 algorithm base

# --- Helper: spaced repetition update ---

def update_flashcard(card, quality):
    # quality: 0-5 (0=fail, 5=perfect)
    if quality < 3:
        card.repetitions = 0
        card.interval = 1
    else:
        card.easiness += (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if card.easiness < 1.3:
            card.easiness = 1.3
        card.repetitions += 1
        if card.repetitions == 1:
            card.interval = 1
        elif card.repetitions == 2:
            card.interval = 6
        else:
            card.interval = int(card.interval * card.easiness)
    card.next_review = datetime.utcnow() + timedelta(days=card.interval)

# --- Routes ---

@app.route('/')
def index():
    # Show stats and link to review/add cards
    total = Flashcard.query.count()
    learned = Flashcard.query.filter(Flashcard.repetitions >= 3).count()
    return render_template('index.html', total=total, learned=learned)

@app.route('/add', methods=['GET', 'POST'])
def add_card():
    if request.method == 'POST':
        word = request.form['word']
        meaning = request.form['meaning']
        if word and meaning:
            new_card = Flashcard(word=word, meaning=meaning)
            db.session.add(new_card)
            db.session.commit()
            flash('Flashcard added!', 'success')
            return redirect(url_for('add_card'))
        flash('Both word and meaning required', 'danger')
    return render_template('add_card.html')

@app.route('/review', methods=['GET', 'POST'])
def review():
    card = Flashcard.query.filter(Flashcard.next_review <= datetime.utcnow()).order_by(Flashcard.next_review).first()
    if not card:
        flash('No cards to review now. Come back later!', 'info')
        return redirect(url_for('index'))

    if request.method == 'POST':
        quality = int(request.form['quality'])  # Expect 0-5
        update_flashcard(card, quality)
        db.session.commit()
        return redirect(url_for('review'))

    return render_template('review.html', card=card)

@app.route('/audio/<int:card_id>')
def audio(card_id):
    card = Flashcard.query.get_or_404(card_id)
    tts = gTTS(card.word, lang='en')
    mp3_fp = io.BytesIO()
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)
    return send_file(mp3_fp, mimetype='audio/mpeg')

# --- Run ---

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
