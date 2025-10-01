import os
from flask import Flask, jsonify
import oci

app = Flask(__name__)

# Signer fonksiyonu - Düzeltilmiş versiyon
def get_signer():
    """
    OCI Signer oluşturur.
    private_key parametresi DOĞRUDAN PEM string bekler,
    cryptography key objesi DEĞİL!
    """
    # Private key'i environment variable'dan direkt al
    private_key_content = os.environ["OCI_PRIVATE_KEY"]
    
    # Eğer \n karakterleri escaped ise düzelt
    if "\\n" in private_key_content:
        private_key_content = private_key_content.replace("\\n", "\n")
    
    # Signer oluştur - private_key_content parametresi kullan
    return oci.signer.Signer(
        tenancy=os.environ["OCI_TENANCY_OCID"],
        user=os.environ["OCI_USER_OCID"],
        fingerprint=os.environ["OCI_FINGERPRINT"],
        private_key_content=private_key_content  # Bu parametre adı doğru!
    )

# Instance başlatma fonksiyonu
def launch_instance():
    try:
        # Signer ile compute client oluştur
        signer = get_signer()
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        
        # Shape configuration (ARM için)
        shape_config = oci.core.models.LaunchInstanceShapeConfigDetails(
            ocpus=1.0,  # 1 OCPU
            memory_in_gbs=6.0  # 6GB RAM
        )
        
        # Instance detayları
        instance_details = oci.core.models.LaunchInstanceDetails(
            availability_domain=os.environ.get("OCI_AVAILABILITY_DOMAIN", "Uocm:ME-ABUDHABI-1-AD-1"),
            compartment_id=os.environ["OCI_COMPARTMENT_OCID"],
            shape="VM.Standard.A1.Flex",
            shape_config=shape_config,  # Flex shape için gerekli
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image",
                image_id=os.environ["OCI_IMAGE_ID"]
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=os.environ["OCI_SUBNET_ID"],
                assign_public_ip=True
            ),
            display_name=os.environ.get("OCI_INSTANCE_NAME", "auto-instance"),
            metadata={
                "ssh_authorized_keys": os.environ.get("OCI_SSH_PUBLIC_KEY", "")
            } if os.environ.get("OCI_SSH_PUBLIC_KEY") else {}
        )
        
        # Instance'ı başlat
        response = compute_client.launch_instance(instance_details)
        
        return {
            "status": "success",
            "message": "Instance launched successfully",
            "instance_id": response.data.id,
            "display_name": response.data.display_name,
            "lifecycle_state": response.data.lifecycle_state
        }
        
    except oci.exceptions.ServiceError as e:
        return {
            "status": "error",
            "error_type": "OCI Service Error",
            "code": e.code,
            "message": e.message,
            "details": str(e)
        }
    except KeyError as e:
        return {
            "status": "error",
            "error_type": "Configuration Error",
            "message": f"Missing environment variable: {str(e)}"
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e)
        }

# Sağlık kontrolü endpoint'i
@app.route("/health")
def health():
    """Render health check için"""
    return jsonify({"status": "healthy"}), 200

# Ana endpoint
@app.route("/")
def home():
    """Ana sayfa - instance başlatır"""
    result = launch_instance()
    
    if result["status"] == "success":
        return jsonify(result), 200
    else:
        return jsonify(result), 500

# Instance durumunu kontrol et
@app.route("/check/<instance_id>")
def check_instance(instance_id):
    """Belirli bir instance'ın durumunu kontrol et"""
    try:
        signer = get_signer()
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        
        response = compute_client.get_instance(instance_id)
        
        return jsonify({
            "status": "success",
            "instance_id": response.data.id,
            "display_name": response.data.display_name,
            "lifecycle_state": response.data.lifecycle_state,
            "availability_domain": response.data.availability_domain,
            "time_created": str(response.data.time_created)
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Tüm instance'ları listele
@app.route("/list")
def list_instances():
    """Compartment'taki tüm instance'ları listele"""
    try:
        signer = get_signer()
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        
        instances = compute_client.list_instances(
            compartment_id=os.environ["OCI_COMPARTMENT_OCID"]
        )
        
        instance_list = [{
            "id": inst.id,
            "display_name": inst.display_name,
            "lifecycle_state": inst.lifecycle_state,
            "shape": inst.shape
        } for inst in instances.data]
        
        return jsonify({
            "status": "success",
            "count": len(instance_list),
            "instances": instance_list
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Instance durdur
@app.route("/stop/<instance_id>")
def stop_instance(instance_id):
    """Instance'ı durdur"""
    try:
        signer = get_signer()
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        
        compute_client.instance_action(instance_id, "STOP")
        
        return jsonify({
            "status": "success",
            "message": f"Instance {instance_id} stopping..."
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Instance başlat
@app.route("/start/<instance_id>")
def start_instance(instance_id):
    """Instance'ı başlat"""
    try:
        signer = get_signer()
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        
        compute_client.instance_action(instance_id, "START")
        
        return jsonify({
            "status": "success",
            "message": f"Instance {instance_id} starting..."
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Instance sil
@app.route("/terminate/<instance_id>")
def terminate_instance(instance_id):
    """Instance'ı kalıcı olarak sil"""
    try:
        signer = get_signer()
        compute_client = oci.core.ComputeClient(config={}, signer=signer)
        
        compute_client.terminate_instance(instance_id)
        
        return jsonify({
            "status": "success",
            "message": f"Instance {instance_id} terminating..."
        }), 200
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
