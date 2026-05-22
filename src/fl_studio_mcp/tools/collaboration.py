"""
Webhook & Collaboration integration for FL Studio MCP.
Allows zipping projects and syncing sessions via webhooks.
"""
import os
import json
import logging
import zipfile
from typing import Dict, Any

logger = logging.getLogger(__name__)

def fl_sync_session(project_dir: str, webhook_url: str, message: str = "New beat finished!", dry_run: bool = False) -> str:
    """
    Zips the project directory and sends an alert via Webhook.
    """
    if dry_run:
        return json.dumps({
            "status": "success",
            "message": f"DRY RUN: Synced {project_dir} to {webhook_url} with message: {message}"
        })

    try:
        import requests
    except ImportError:
        return json.dumps({"status": "error", "message": "requests not installed."})

    if not os.path.exists(project_dir):
        return json.dumps({"status": "error", "message": f"Project directory not found: {project_dir}"})

    try:
        zip_path = os.path.join(project_dir, "project_sync.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    # Avoid zipping the zip itself
                    if file == "project_sync.zip":
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, project_dir)
                    zipf.write(file_path, arcname)
                    
        logger.info(f"Project zipped successfully to {zip_path}")
        
        # Send Webhook
        payload = {
            "content": f"🚀 **FL Studio MCP Sync**\n{message}\n*Project archive generated locally.*"
        }
        
        response = requests.post(webhook_url, json=payload, timeout=5)
        if response.status_code in (200, 204):
            return json.dumps({
                "status": "success",
                "message": f"Session synced! Zip created at {zip_path} and webhook fired."
            })
        else:
            return json.dumps({
                "status": "error",
                "message": f"Webhook returned status code {response.status_code}"
            })

    except Exception as e:
        logger.error(f"Collaboration sync error: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def register(mcp) -> None:
    """Register Collaboration tools."""
    mcp.tool()(fl_sync_session)
