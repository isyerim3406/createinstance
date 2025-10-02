import os
from flask import Flask, jsonify
import oci
import tempfile
import base64
import time
import requests
import datetime
import threading

app = Flask(__name__)

# --- TELEGRAM BİLDİRİM FONKSİYONU ---
def send_telegram_message(message):
    """Telegram üzerinden bildirim mesajı gönderir."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Telegram BOT_TOKEN veya CHAT_ID ayarlanmamış. Bildirim atlanıyor.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()
        print("Telegram bildirimi başarıyla gönderildi.")
    except Exception as e:
        print(f"Telegram bildirimi gönderme başarısız oldu: {e}")

# --- SIGNER VE KONFİGÜRASYON FONKSİYONU ---

def get_signer():
    """Ortam değişkenlerinden OCI kimlik doğrulama yapılandırmasını oluşturur."""
    
    if "OCI_PRIVATE_KEY_BASE64" in os.environ:
        private_key_encoded = os.environ["OCI_PRIVATE_KEY_BASE64"]
        private_key = base64.b64decode(private_key_encoded).decode('utf-8')
    elif "OCI_PRIVATE_KEY" in os.environ:
        private_key = os.environ["OCI_PRIVATE_KEY"]
        if "\\n" in private_key:
            private_key = private_key.replace("\\n", "\n")
    else:
        raise KeyError("OCI_PRIVATE_KEY or OCI_PRIVATE_KEY_BASE64 environment variable is missing.")
    
    try:
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pem', encoding='utf-8', newline=None) as key_file:
            key_file.write(private_key.strip()) 
            key_file_path = key_file.name
    except Exception as e:
        raise IOError(f"Error writing private key to temp file: {str(e)}")
    
    config = {
        "tenancy": os.environ["OCI_TENANCY_OCID"].strip(),
        "user": os.environ["OCI_USER_OCID"].strip(),
        "fingerprint": os.environ["OCI_FINGERPRINT"].strip(),
        "key_file": key_file_path,
        "region": os.environ.get("OCI_REGION", "me-abudhabi-1").strip()
    }
    return config

# --- ANA İŞLEV (VM BAŞLATMA) ---

def launch_instance_attempt():
    """OCI'da tek bir VM başlatma denemesi yapar."""
    try:
        config = get_signer()
        compute_client = oci.core.ComputeClient(config)
        
        # Flex Shape'i tam sayı olarak tanımlar
        shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=1,
            memory_in_gbs=6
        )
        
        # Instance detayları
        instance_details = oci.core.models.LaunchInstanceDetails(
            availability_domain=os.environ.get("OCI_AVAILABILITY_DOMAIN").strip(),
            compartment_id=os.environ["OCI_COMPARTMENT_OCID"].strip(),
            shape="VM.Standard.A1.Flex",
            shape_config=shape_config,
            
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=os.environ["OCI_IMAGE_ID"].strip()
            ),
            
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=os.environ["OCI_SUBNET_ID"].strip(),
                assign_public_ip=True
            ),
            
            display_name=os.environ.get("OCI_INSTANCE_NAME", "auto-instance").strip(),
            
            metadata={
                "ssh_authorized_keys": os.environ.get("OCI_SSH_PUBLIC_KEY", "").strip()
            } if os.environ.get("OCI_SSH_PUBLIC_KEY") else {}
        )
        
        response = compute_client.launch_instance(instance_details)
        
        # Başarı
        return_data = {
            "status": "success",
            "message": f"VM Başarıyla Başlatma İsteği Gönderildi. ID: {response.data.id}",
            "instance_id": response.data.id,
            "lifecycle_state": response.data.lifecycle_state
        }
        
        # BAŞARILI BİLDİRİMİ GÖNDERİLİYOR
        success_message = (
            f"🎉 *VM Başlatma Başarılı!*\n"
            f"----------------------------------------\n"
            f"VM Adı: {response.data.display_name}\n"
            f"Durum: `{response.data.lifecycle_state}`\n"
            f"Instance ID: `{response.data.id}`\n"
            f"Lütfen harici tetikleyiciyi durdurun (UptimeRobot, vb.)."
        )
        send_telegram_message(success_message)
        
        return return_data

    except oci.exceptions.ServiceError as e:
        # --- GMT+3 ZAMAN DİLİMİ DÜZELTMESİ ---
        current_utc_time = datetime.datetime.now(datetime.timezone.utc)
        gmt_plus_3_time = current_utc_time + datetime.timedelta(hours=3)
        gmt_plus_3_formatted = gmt_plus_3_time.strftime('%Y-%m-%d %H:%M:%S')
        
        # TooManyRequests Hatası (Oran Limiti)
        if e.code == "TooManyRequests":
            error_message = (
                f"🚨 *ACIYARACAK ORAN LİMİTİ HATASI!*\n"
                f"---------------------------------------------------\n"
                f"**KOD:** `{e.code}`\n"
                f"**MESAJ:** OCI sizi geçici olarak engelledi. Kısır döngüye girmeyin.\n"
                f"**GEREKEN EYLEM:** Lütfen UptimeRobot'ı hemen durdurun.\n"
                f"15 dakika sonra tekrar başlatın (ve sıklığı 10 dakikada bir tutun)."
            )
            send_telegram_message(error_message) # Telegram bildirimi gönder
            return {
                "status": "error",
                "error_type": "RateLimitError",
                "message": f"Too many requests. OCI sizi engelledi. UptimeRobot'ı durdurun. Son deneme (GMT+3): {gmt_plus_3_formatted}",
            }
        
        # Kapasite Hatası
        if "Out of host capacity" in e.message:
            return {
                "status": "error",
                "error_type": "CapacityError",
                "message": f"Out of host capacity. Tekrar deneyin. Son deneme (GMT+3): {gmt_plus_3_formatted}",
            }
            
        # Diğer OCI hataları
        return {
            "status": "error",
            "error_type": "OCI Service Error",
            "message": e.message,
            "code": e.code
        }
    except Exception as e:
        # Yapılandırma hataları (KeyError gibi)
        return {"status": "error", "error_type": type(e).__name__, "message": str(e)}

# --- FLASK YOLLARI (ROUTES) ---

@app.route("/health")
def health():
    """Render sağlık kontrolü için (VM denemesi yapmaz)"""
    return jsonify({"status": "healthy"}), 200

@app.route("/")
def home():
    """Ana yol: Tek bir VM başlatma denemesi yapar."""
    result = launch_instance_attempt()
    
    http_status = 200
    if result["status"] == "error":
        http_status = 400
        
    return jsonify(result), http_status

@app.route("/debug/config")
def debug_config():
    """Environment variable'ları kontrol et (güvenli)"""
    return jsonify({
        "tenancy": os.environ.get("OCI_TENANCY_OCID", "NOT_SET")[:20] + "...",
        "user": os.environ.get("OCI_USER_OCID", "NOT_SET")[:20] + "...",
        "fingerprint": os.environ.get("OCI_FINGERPRINT", "NOT_SET"),
        "region": os.environ.get("OCI_REGION", "me-abudhabi-1"),
        "compartment": os.environ.get("OCI_COMPARTMENT_OCID", "NOT_SET")[:20] + "...",
        "ad": os.environ.get("OCI_AVAILABILITY_DOMAIN", "NOT_SET"),
    }), 200

@app.route("/debug/auth")
def debug_auth():
    """OCI authentication'ı test et"""
    try:
        config = get_signer()
        identity_client = oci.identity.IdentityClient(config)
        user = identity_client.get_user(os.environ["OCI_USER_OCID"].strip())
        
        return jsonify({
            "status": "success",
            "message": "Authentication successful",
            "user_name": user.data.name,
            "user_id": user.data.id
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }), 400

# --- UYGULAMA BAŞLANGICI ---

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
