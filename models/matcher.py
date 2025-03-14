from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import os
import pandas as pd
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class Dog:
    def __init__(self, name, size, age, energy):
        self.name = name
        self.size = size
        self.age = age
        self.energy = energy

class Shelter:
    def __init__(self, name, size_range, age_range, energy_range):
        self.name = name
        self.size_min, self.size_max = size_range
        self.age_min, self.age_max = age_range
        self.energy_min, self.energy_max = energy_range
    
    def is_suitable(self, dog):
        return (self.size_min <= dog.size <= self.size_max and
                self.age_min <= dog.age <= self.age_max and
                self.energy_min <= dog.energy <= self.energy_max)

def load_data(dogs_path, shelters_path):
    dogs_df = pd.read_csv(dogs_path)
    shelters_df = pd.read_csv(shelters_path)
    
    dogs = [Dog(row['Dog Name'], int(row['Size (1-5)']), int(row['Age (years)']), int(row['Energy Level (1-5)'])) 
            for _, row in dogs_df.iterrows()]
    
    shelters = [Shelter(row['Shelter Name'],
                       (int(row['Size Min']), int(row['Size Max'])),
                       (int(row['Age Min']), int(row['Age Max'])),
                       (int(row['Energy Min']), int(row['Energy Max'])))
                for _, row in shelters_df.iterrows()]
    
    return dogs, shelters

def find_matches(dogs_path, shelters_path):
    dogs, shelters = load_data(dogs_path, shelters_path)
    
    all_matches = []
    for dog in dogs:
        suitable_shelters = [shelter for shelter in shelters if shelter.is_suitable(dog)]
        
        if suitable_shelters:
            dog_matches = {
                'dog_name': dog.name,
                'dog_size': dog.size,
                'dog_age': dog.age,
                'dog_energy': dog.energy,
                'shelters': [shelter.name for shelter in suitable_shelters]
            }
            all_matches.append(dog_matches)
    
    return all_matches

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload_files', methods=['POST'])
def upload_files():
    # Check if files were uploaded
    if 'dogs_file' not in request.files or 'shelters_file' not in request.files:
        flash('Both files are required')
        return redirect(request.url)
    
    dogs_file = request.files['dogs_file']
    shelters_file = request.files['shelters_file']
    
    # Save files to uploads folder
    dogs_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(dogs_file.filename))
    shelters_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(shelters_file.filename))
    
    dogs_file.save(dogs_path)
    shelters_file.save(shelters_path)
    
    # Store file paths in session
    session['dogs_path'] = dogs_path
    session['shelters_path'] = shelters_path
    
    # Process files and get matches
    matches = find_matches(dogs_path, shelters_path)
    session['matches'] = matches
    
    return redirect(url_for('questionnaire', match_index=0))

@app.route('/questionnaire/<int:match_index>', methods=['GET', 'POST'])
def questionnaire(match_index):
    matches = session.get('matches', [])
    
    # Check if we've completed all matches
    if match_index >= len(matches):
        return redirect(url_for('results'))
    
    current_match = matches[match_index]
    dog_name = current_match['dog_name']
    shelters = current_match['shelters']
    
    if request.method == 'POST':
        # Store questionnaire responses
        responses = {}
        for shelter in shelters:
            shelter_responses = {}
            for i in range(1, 6):
                question_key = f"{shelter}_q{i}"
                if question_key in request.form:
                    shelter_responses[f"Q{i}"] = request.form[question_key]
            responses[shelter] = shelter_responses
        
        # Update match with responses
        current_match['responses'] = responses
        matches[match_index] = current_match
        session['matches'] = matches
        
        # Move to next match
        return redirect(url_for('questionnaire', match_index=match_index + 1))
    
    return render_template('questionnaire.html', 
                          match=current_match,
                          shelters=shelters,
                          match_index=match_index,
                          total_matches=len(matches))

@app.route('/results')
def results():
    matches = session.get('matches', [])
    
    # Generate CSV file
    results_df = pd.DataFrame([
        {
            'Dog Name': match['dog_name'],
            'Size': match['dog_size'],
            'Age': match['dog_age'],
            'Energy Level': match['dog_energy'],
            'Matching Shelters': ', '.join(match['shelters']),
            'Questionnaire Responses': '\n\n'.join([
                f"{shelter}:\n" + '\n'.join([f"{q}: {a}" for q, a in responses.items()]) 
                for shelter, responses in match.get('responses', {}).items()
            ])
        }
        for match in matches
    ])
    
    results_path = os.path.join(app.config['UPLOAD_FOLDER'], 'adoption_report.csv')
    results_df.to_csv(results_path, index=False)
    
    return render_template('results.html', 
                          matches=matches,
                          results_path=results_path)

@app.route('/download')
def download_report():
    results_path = os.path.join(app.config['UPLOAD_FOLDER'], 'adoption_report.csv')
    return send_file(results_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
