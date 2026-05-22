import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from fl_studio_mcp.tools.vst_scanner import get_fl_user_data_path

class PresetLibrarian:
    """Manages the VST presets catalog and GUI click coordinates in a local JSON database."""

    def __init__(self, database_path: Optional[Path] = None):
        if database_path:
            self.db_path = database_path
        else:
            # Attempt to put in FL Studio user presets database, fallback to workspace local
            try:
                fl_path = get_fl_user_data_path()
                self.db_path = fl_path / "Presets" / "mcp_presets.json"
                # Ensure the parent Presets folder exists
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                self.db_path = Path(".fl_studio_mcp") / "mcp_presets.json"
                self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._load_database()

    def _load_database(self) -> None:
        """Loads database from file, or creates an empty structure if missing."""
        if self.db_path.exists():
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {"presets": []}
        else:
            self.data = {"presets": []}

    def _save_database(self) -> None:
        """Saves the active preset data back to the JSON file."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def catalog_preset(
        self,
        vst_name: str,
        preset_name: str,
        x: int,
        y: int,
        category: str = "Unsorted",
        tags: Optional[List[str]] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Save or update VST preset click coordinates and tags."""
        norm_vst = vst_name.strip()
        norm_preset = preset_name.strip()
        tags_list = [t.strip().lower() for t in (tags or []) if t.strip()]

        preset_entry = {
            "vst_name": norm_vst,
            "preset_name": norm_preset,
            "x": x,
            "y": y,
            "category": category.strip(),
            "tags": tags_list,
            "notes": notes.strip()
        }

        # Remove existing if exists to prevent duplicates
        self.data["presets"] = [
            p for p in self.data["presets"]
            if not (p["vst_name"].lower() == norm_vst.lower() and p["preset_name"].lower() == norm_preset.lower())
        ]

        self.data["presets"].append(preset_entry)
        self._save_database()
        return preset_entry

    def search_presets(
        self,
        query: Optional[str] = None,
        vst_name: Optional[str] = None,
        tag: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search registered VST presets matching filters."""
        results = []
        q_lower = query.strip().lower() if query else None
        vst_lower = vst_name.strip().lower() if vst_name else None
        tag_lower = tag.strip().lower() if tag else None
        cat_lower = category.strip().lower() if category else None

        for p in self.data["presets"]:
            # Filter by VST name (exact or substring)
            if vst_lower and vst_lower not in p["vst_name"].lower():
                continue
            
            # Filter by category
            if cat_lower and cat_lower != p["category"].lower():
                continue
            
            # Filter by specific tag
            if tag_lower and tag_lower not in p["tags"]:
                continue
            
            # Filter by keyword query across name, category, notes, and tags
            if q_lower:
                match = (
                    q_lower in p["preset_name"].lower() or
                    q_lower in p["vst_name"].lower() or
                    q_lower in p["category"].lower() or
                    q_lower in p["notes"].lower() or
                    any(q_lower in t for t in p["tags"])
                )
                if not match:
                    continue

            results.append(p)
        return results

    def get_preset(self, vst_name: str, preset_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve coordinates and detail of a specific VST preset."""
        norm_vst = vst_name.strip().lower()
        norm_preset = preset_name.strip().lower()
        for p in self.data["presets"]:
            if p["vst_name"].lower() == norm_vst and p["preset_name"].lower() == norm_preset:
                return p
        return None

    def delete_preset(self, vst_name: str, preset_name: str) -> bool:
        """Delete a VST preset registry entry."""
        norm_vst = vst_name.strip().lower()
        norm_preset = preset_name.strip().lower()
        original_count = len(self.data["presets"])
        self.data["presets"] = [
            p for p in self.data["presets"]
            if not (p["vst_name"].lower() == norm_vst and p["preset_name"].lower() == norm_preset)
        ]
        success = len(self.data["presets"]) < original_count
        if success:
            self._save_database()
        return success
