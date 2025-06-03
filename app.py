from flask import Flask, request, render_template, jsonify
import json, time, os

print("🚀 Flask app started (updated version)")

app = Flask(__name__)

sensor_file = 'sensor.json'
threshold_file = 'thresholds.json'
manual_file = 'manual.json'

esp_last_seen = 0

def load(file, default):
    try:
        with open(file) as f:
            return json.load(f)
    except:
        return default

def save(file, data):
    with open(file, 'w') as f:
        json.dump(data, f)

default_relays = {"relay1": "auto", "relay2": "auto", "relay3": "auto"}
if not os.path.exists(manual_file):
    save(manual_file, default_relays)
else:
    relays = load(manual_file, {})
    if not all(k in relays for k in ["relay1", "relay2", "relay3"]):
        save(manual_file, default_relays)

latest_data = load(sensor_file, {
    "temperature": 0, "humidity": 0, "soil": 0, "time": "--",
    "relay1": "auto", "relay2": "auto", "relay3": "auto"
})

@app.route('/')
def dashboard():
    return render_template('dashboard.html',
        sensors=load(sensor_file, {}),
        thresholds=load(threshold_file, {}),
        relays=load(manual_file, {})
    )

@app.route('/sensor_data', methods=['POST'])
def sensor_data():
    print("📥 Incoming POST to /sensor_data")
    print("📄 Raw body:", request.data.decode('utf-8'))

    try:
        data = request.get_json(force=True)
        print("📦 Parsed JSON:", data)
        if data:
            save(sensor_file, data)
            print("💾 Saved to sensor.json")
            global latest_data
            latest_data = data
            return "OK", 200
        else:
            print("❌ No data parsed")
            return "Bad JSON", 400
    except Exception as e:
        print("❌ Error:", e)
        return f"Error: {str(e)}", 400

@app.route('/sensor_data_live')
def sensor_data_live():
    return jsonify(latest_data)

@app.route('/get_thresholds')
def get_thresholds():
    return jsonify(load(threshold_file, {}))

@app.route('/get_relays')
def get_relays():
    relays = load(manual_file, {})
    print("📤 /get_relays returning:", relays)
    return jsonify({k: v.lower() for k, v in relays.items()})

@app.route('/update_thresholds', methods=['POST'])
def update_thresholds():
    save(threshold_file, request.form.to_dict())
    return "Updated"

@app.route('/update_relays', methods=['POST'])
def update_relays():
    save(manual_file, request.json)
    print("📝 Manual relay update:", request.json)
    return jsonify(status="ok", refresh_relay_now=True)

@app.route('/force_refresh')
def force_refresh():
    return "Triggered"

@app.route('/ping', methods=['POST'])
def ping():
    global esp_last_seen
    esp_last_seen = time.time()
    return '', 204

@app.route('/esp_status')
def esp_status():
    return jsonify({'status': 'online' if time.time() - esp_last_seen < 30 else 'offline'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
