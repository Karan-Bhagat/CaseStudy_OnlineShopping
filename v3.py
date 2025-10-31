#!/usr/bin/env python3
"""
mdis_yaml_validator_ui_match.py

Single-file Tkinter MDIS YAML Editor + Validator
UI arranged to match the screenshot: purple header, horizontal toolbar,
left black Application Log with red Clear Log button, large YAML Editor on right.
Keeps the same functionality (beautify/validate/save/gitlab) as before.

Dependencies (optional for fuller behavior):
  pip install ruamel.yaml pyyaml jsonschema python-gitlab
"""
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter.font as tkfont
from pathlib import Path
import json, os, sys, datetime, threading, re, webbrowser, logging
from logging.handlers import RotatingFileHandler

# Optional libs
try:
    from ruamel.yaml import YAML
    YAML_AVAILABLE = True
except Exception:
    YAML_AVAILABLE = False
try:
    import yaml as pyyaml
    PYYAML_AVAILABLE = True
except Exception:
    PYYAML_AVAILABLE = False
try:
    import jsonschema
    JSONSCHEMA_AVAILABLE = True
except Exception:
    JSONSCHEMA_AVAILABLE = False
try:
    import gitlab
    GITLAB_AVAILABLE = True
except Exception:
    GITLAB_AVAILABLE = False

# Paths/config
HOME = Path.home()
CONFIG_PATH = HOME / ".mdis_yaml_validator_config.json"
LOG_DIR = HOME / ".mdis_yaml_validator_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"mdis_validator_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Logging
logger = logging.getLogger("mdis_validator")
logger.setLevel(logging.DEBUG)
fh = RotatingFileHandler(str(LOG_FILE), maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
fh.setLevel(logging.DEBUG)
fh_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
fh.setFormatter(fh_formatter)
logger.addHandler(fh)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(fh_formatter)
logger.addHandler(ch)

class TextWidgetHandler(logging.Handler):
    """Concise logger output to GUI log widget (INFO/WARN/ERROR)."""
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setLevel(logging.INFO)
    def emit(self, record):
        try:
            msg = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [{record.levelname}] {record.getMessage()}\n"
            def append():
                try:
                    self.text_widget.configure(state='normal')
                    self.text_widget.insert(tk.END, msg)
                    self.text_widget.configure(state='disabled')
                    self.text_widget.see(tk.END)
                except Exception:
                    pass
            self.text_widget.after(0, append)
        except Exception:
            pass

# --- Services: Beautify & Validate (kept similar to earlier) ---
class BeautifyService:
    @staticmethod
    def beautify(yaml_content: str) -> str:
        try:
            if YAML_AVAILABLE:
                yaml = YAML()
                try:
                    yaml.preserve_quotes = True
                except Exception:
                    pass
                yaml.indent(mapping=2, sequence=4, offset=2)
                from io import StringIO
                data = yaml.load(yaml_content)
                if data is None:
                    return "❌ No valid YAML content to beautify."
                s = StringIO()
                yaml.dump(data, s)
                out = s.getvalue()
                return out.rstrip() + "\n" if out.strip() else "❌ Beautify failed (empty output)."
            elif PYYAML_AVAILABLE:
                data = pyyaml.safe_load(yaml_content)
                if data is None:
                    return "❌ No valid YAML content to beautify."
                return pyyaml.safe_dump(data, sort_keys=False, indent=2, default_flow_style=False)
            else:
                return "❌ No YAML library available. Install ruamel.yaml or PyYAML."
        except Exception as e:
            logger.exception("Beautify failed")
            return f"❌ Beautify error: {e}"

class FileService:
    @staticmethod
    def get_tag_value(file_content: str, tag_name: str) -> str:
        try:
            if YAML_AVAILABLE:
                ruamel_yaml = YAML()
                parsed = ruamel_yaml.load(file_content)
            elif PYYAML_AVAILABLE:
                parsed = pyyaml.safe_load(file_content)
            else:
                return "Unknown"
            if isinstance(parsed, dict):
                v = parsed.get(tag_name)
                return str(v) if v is not None else "Unknown"
            return "Unknown"
        except Exception:
            return "Unknown"

class YamlValidationService:
    REQUIRED_FIELDS = ["pipeline_id", "template_id", "spoke_name"]
    @staticmethod
    def validate(yaml_content: str):
        try:
            template_id = FileService.get_tag_value(yaml_content, "template_id")
            if not template_id or template_id == "Unknown":
                if YAML_AVAILABLE:
                    parsed = YAML().load(yaml_content)
                elif PYYAML_AVAILABLE:
                    parsed = pyyaml.safe_load(yaml_content)
                else:
                    parsed = None
                if isinstance(parsed, dict):
                    template_id = parsed.get("template_id", "Unknown")
            if not template_id or template_id == "Unknown":
                return False, "❌ Missing or invalid 'template_id'", None
            schema_file = Path.cwd() / "schema" / f"{template_id}.json"
            if JSONSCHEMA_AVAILABLE and schema_file.exists():
                try:
                    data = YAML().load(yaml_content) if YAML_AVAILABLE else pyyaml.safe_load(yaml_content)
                    schema = json.loads(schema_file.read_text(encoding='utf-8'))
                    jsonschema.validate(instance=data, schema=schema)
                    return True, f"✅ YAML is valid (schema validated)\nTemplate: {template_id}", None
                except jsonschema.ValidationError as ve:
                    ln = None
                    try:
                        path = list(ve.path)
                        if path:
                            last = str(path[-1])
                            pat = r'^[ \t-]*' + re.escape(last) + r'\s*:'
                            for i, line in enumerate(yaml_content.splitlines(), start=1):
                                if re.search(pat, line):
                                    ln = i; break
                    except Exception:
                        ln = None
                    return False, f"❌ Schema validation failed: {ve.message}", ln
                except Exception as ex:
                    return False, f"❌ Error during schema validation: {ex}", None
            try:
                data = YAML().load(yaml_content) if YAML_AVAILABLE else pyyaml.safe_load(yaml_content)
            except Exception as e:
                return False, f"❌ YAML parse error: {e}", None
            if not isinstance(data, dict):
                return False, "❌ YAML root is not a mapping/dictionary.", None
            missing = [k for k in YamlValidationService.REQUIRED_FIELDS if k not in data or not data[k]]
            if missing:
                ln = None
                for m in missing:
                    pat = r'^[ \t-]*' + re.escape(m) + r'\s*:'
                    for i, line in enumerate(yaml_content.splitlines(), start=1):
                        if re.search(pat, line):
                            ln = i; break
                    if ln: break
                msg = f"❌ Missing required fields: {', '.join(missing)}"
                if ln: msg += f"\nLikely at line {ln}"
                return False, msg, ln
            return True, f"✅ YAML is valid (structural checks passed)\nTemplate: {FileService.get_tag_value(yaml_content,'template_id')}", None
        except Exception as e:
            logger.exception("Validation error")
            return False, f"❌ Validation error: {e}", None

# GitLab helper (same simplified behavior as before)
class GitLabHelper:
    def __init__(self, config):
        self.config = config
        self.gl = None
        if GITLAB_AVAILABLE:
            token = config.get("gitlab_token")
            url = config.get("gitlab_url", "https://gitlab.com")
            if token:
                try:
                    self.gl = gitlab.Gitlab(url, private_token=token)
                    self.gl.auth()
                    logger.info("Authenticated to GitLab")
                except Exception as e:
                    logger.warning(f"GitLab auth failed: {e}")
                    self.gl = None
    def create_branch_and_commit_and_mr(self, project_id, branch_name, base_branch, files_dict, mr_title, mr_desc):
        if not GITLAB_AVAILABLE:
            return False, "python-gitlab not installed"
        if not self.gl:
            return False, "Not authenticated to GitLab"
        try:
            project = self.gl.projects.get(project_id)
        except Exception as e:
            return False, f"Failed to open project {project_id}: {e}"
        try:
            project.branches.create({'branch': branch_name, 'ref': base_branch})
        except Exception:
            pass
        actions = []
        for path_in_repo, content in files_dict.items():
            actions.append({'action': 'create', 'file_path': path_in_repo, 'content': content})
        try:
            commit_data = {'branch': branch_name, 'commit_message': f"Add files for MR: {mr_title}", 'actions': actions}
            project.commits.create(commit_data)
        except Exception:
            actions = [{'action': 'update', 'file_path': k, 'content': v} for k,v in files_dict.items()]
            commit_data = {'branch': branch_name, 'commit_message': f"Update files for MR: {mr_title}", 'actions': actions}
            project.commits.create(commit_data)
        try:
            mr = project.mergerequests.create({'source_branch': branch_name, 'target_branch': base_branch, 'title': mr_title, 'description': mr_desc})
            return True, mr.web_url
        except Exception as e:
            return False, f"Failed to create MR: {e}"

# --- Main App UI matching the screenshot ---
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("MDIS - YAML Editor + Validator")
        self.root.geometry("1365x768")
        self.config = self._load_config()
        self.current_path = None
        self.font_family = tk.StringVar(value=self.config.get("font_family", "Consolas"))
        self.font_size = tk.IntVar(value=self.config.get("font_size", 11))
        self._build_ui()
        logger.info("MDIS GUI - YAML Editor Application Loaded")
        logger.info("You can hook your beautify/validate methods into this UI template.")
        self._update_status("Ready")

    def _build_ui(self):
        # TOP BANNER
        banner = tk.Frame(self.root, height=88, bg="#5A287D")
        banner.pack(fill="x")
        banner.pack_propagate(False)
        left_logo = tk.Label(banner, text="NatWest Group", fg="white", bg="#5A287D", font=("Segoe UI", 28, "bold"))
        left_logo.pack(side="left", padx=20, pady=12)
        right_title = tk.Label(banner, text="MDIS - YAML Editor", fg="white", bg="#5A287D", font=("Segoe UI", 18, "bold"))
        right_title.pack(side="right", padx=24, pady=14)

        # HORIZONTAL TOOLBAR (buttons arranged horizontally beneath banner)
        toolbar = tk.Frame(self.root, height=48, bg="#f0f0f0")
        toolbar.pack(fill="x", padx=10, pady=(8,6))
        btn_specs = [
            ("Open", self.open_file),
            ("Save", self.save_file),
            ("Save As", self.save_as_file),
            ("Format YAML", self.beautify_yaml),
            ("Validate YAML", self.validate_yaml),
            ("GitLab Profile", self.open_gitlab_user_dialog),
            ("Create Merge Request", self._create_mr_flow),
            ("Change Font", self.font_chooser),
            ("Clear Log", self.clear_log),
        ]
        for (txt, cmd) in btn_specs:
            b = tk.Button(toolbar, text=txt, width=14, command=cmd, relief="raised")
            b.pack(side="left", padx=6)

        # MAIN CONTENT: left log column and right editor
        main = tk.Frame(self.root)
        main.pack(fill="both", expand=True, padx=10, pady=(0,8))

        # LEFT: Application Log
        left_col = tk.Frame(main, width=320)
        left_col.pack(side="left", fill="y", padx=(0,10))
        left_col.pack_propagate(False)
        lbl_log = tk.Label(left_col, text="Application Log", font=("Segoe UI", 12, "bold"))
        lbl_log.pack(anchor="nw", pady=(2,6))
        # black log area
        self.log_box = scrolledtext.ScrolledText(left_col, width=40, height=30, state='disabled', wrap='word')
        self.log_box.pack(fill="both", expand=True, padx=4)
        self.log_box.configure(font=("Consolas", 10), bg="#111111", fg="#f5f5f5", insertbackground="#f5f5f5")
        # attach GUI logger
        self.text_handler = TextWidgetHandler(self.log_box)
        self.text_handler.setFormatter(fh_formatter)
        logger.addHandler(self.text_handler)
        # small clear log button bottom-left (red)
        clear_frame = tk.Frame(left_col, height=34)
        clear_frame.pack(fill="x", pady=6)
        clear_frame.pack_propagate(False)
        self.clear_log_btn = tk.Button(clear_frame, text="Clear Log", bg="#e76c6c", fg="white", command=self.clear_log)
        self.clear_log_btn.pack(side="left", padx=6)

        # RIGHT: YAML Editor title + framed editor
        right_col = tk.Frame(main)
        right_col.pack(side="left", fill="both", expand=True)
        lbl_editor = tk.Label(right_col, text="YAML Editor", font=("Segoe UI", 12, "bold"))
        lbl_editor.pack(anchor="nw", pady=(2,6))
        # framed border to resemble screenshot
        editor_border = tk.Frame(right_col, bd=1, relief="solid")
        editor_border.pack(fill="both", expand=True)
        self.editor = scrolledtext.ScrolledText(editor_border, wrap='none')
        self.editor.pack(fill="both", expand=True)
        self.editor.configure(font=("Consolas", 12), bg="white", fg="#000000", insertbackground="#000000")

        # BOTTOM status
        status_frame = tk.Frame(self.root, height=20)
        status_frame.pack(fill="x", side="bottom")
        self.status_label = tk.Label(status_frame, text="Ready", anchor="w")
        self.status_label.pack(side="left", padx=6)

        # keyboard shortcuts
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: self.save_file())

    # ------------------- ACTIONS -------------------
    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("YAML files","*.yaml *.yml"),("All files","*.*")])
        if not path:
            return
        try:
            content = Path(path).read_text(encoding='utf-8')
            self.editor.config(state='normal')
            self.editor.delete("1.0", tk.END)
            self.editor.insert(tk.END, content)
            self.current_path = path
            logger.info(f"Opened file {path}")
            self._update_status(f"Opened: {Path(path).name}")
        except Exception as e:
            logger.exception("Failed to open file")
            messagebox.showerror("Open error", f"Failed to open file: {e}")

    def save_file(self):
        if not self.current_path:
            return self.save_as_file()
        try:
            Path(self.current_path).write_text(self.editor.get("1.0", tk.END), encoding='utf-8')
            logger.info(f"Saved file {self.current_path}")
            self._update_status(f"Saved: {Path(self.current_path).name}")
            messagebox.showinfo("Saved", f"Saved: {self.current_path}")
        except Exception as e:
            logger.exception("Save failed")
            messagebox.showerror("Save error", f"Failed to save file: {e}")

    def save_as_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".yaml", filetypes=[("YAML files","*.yaml"),("All files","*.*")])
        if not path:
            return
        try:
            Path(path).write_text(self.editor.get("1.0", tk.END), encoding='utf-8')
            self.current_path = path
            logger.info(f"Saved As {path}")
            self._update_status(f"Saved: {Path(path).name}")
            messagebox.showinfo("Saved", f"Saved: {path}")
        except Exception as e:
            logger.exception("Save as failed")
            messagebox.showerror("Save as error", f"Failed to save file: {e}")

    def beautify_yaml(self):
        content = self.editor.get("1.0", tk.END).rstrip()
        if not content:
            messagebox.showwarning("Empty", "Open or paste YAML first")
            return
        formatted = BeautifyService.beautify(content)
        if isinstance(formatted, str) and formatted.startswith("❌"):
            logger.error(f"Beautify failed: {formatted}")
            messagebox.showerror("Beautify error", formatted)
            self._update_status("Beautify failed")
            return
        self.editor.config(state='normal')
        self.editor.delete("1.0", tk.END)
        self.editor.insert(tk.END, formatted)
        logger.info("Beautified YAML")
        self._update_status("Beautified YAML")

    def validate_yaml(self):
        content = self.editor.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Empty", "Open or paste YAML first")
            return False
        ok, msg, ln = YamlValidationService.validate(content)
        logger.info("Validation: " + (msg.splitlines()[0] if msg else "finished"))
        self._update_status((msg.splitlines()[0] if msg else "Validation finished"))
        if ok:
            messagebox.showinfo("Validation", msg)
            return True
        else:
            if ln:
                try:
                    self.editor.tag_remove("errline", "1.0", tk.END)
                    line_start = f"{ln}.0"; line_end = f"{ln}.end"
                    self.editor.tag_add("errline", line_start, line_end)
                    self.editor.tag_config("errline", background="#ffdddd")
                    self.editor.see(line_start)
                except Exception:
                    pass
            messagebox.showerror("Validation", msg)
            return False

    def clear_log(self):
        try:
            self.log_box.configure(state='normal')
            self.log_box.delete("1.0", tk.END)
            self.log_box.configure(state='disabled')
            logger.info("Log cleared by user")
        except Exception:
            logger.exception("Failed clearing GUI log")

    def font_chooser(self):
        chooser = tk.Toplevel(self.root)
        chooser.title("Font chooser")
        tk.Label(chooser, text="Family").grid(row=0, column=0, padx=6, pady=6)
        families = sorted(set(tkfont.families()))
        fam_cb = ttk.Combobox(chooser, values=families, state="readonly")
        fam_cb.set(self.font_family.get())
        fam_cb.grid(row=0, column=1, padx=6, pady=6)
        tk.Label(chooser, text="Size").grid(row=1, column=0, padx=6, pady=6)
        size_spin = tk.Spinbox(chooser, from_=8, to=36, width=6)
        size_spin.delete(0, "end"); size_spin.insert(0, str(self.font_size.get()))
        size_spin.grid(row=1, column=1, padx=6, pady=6)
        def apply_font():
            self.font_family.set(fam_cb.get())
            try:
                self.font_size.set(int(size_spin.get()))
            except Exception:
                self.font_size.set(11)
            self.editor.configure(font=(self.font_family.get(), self.font_size.get()))
            chooser.destroy()
            logger.info(f"Font changed to {self.font_family.get()} {self.font_size.get()}")
        tk.Button(chooser, text="Apply", command=apply_font).grid(row=2, column=0, columnspan=2, pady=8)

    def open_gitlab_user_dialog(self):
        dlg = GitLabUserProfileDialog(self.root, self.config, self)
        dlg.grab_set()

    def _create_mr_flow(self):
        logger.info("Creation of Pull Request Validation Initiated")
        yaml_text = self.editor.get("1.0", tk.END)
        if yaml_text is None or yaml_text.strip() == "":
            logger.warning("YAML content is empty, aborting validation and Pull Request")
            messagebox.showwarning("Empty YAML", "YAML content is empty. Please enter or open a YAML file before proceeding.")
            return
        if not self.validate_yaml():
            return
        pr = PullRequestDialogTk(self.root, self)
        pr.wait_window()
        if not pr.confirmed:
            return
        attachments = self.config.get("_attachments", {})
        files_dict = dict(attachments)
        if pr.include_current_yaml:
            fname = Path(self.current_path).name if self.current_path else "pasted.yaml"
            files_dict[f"mdis_manifests/{fname}"] = self.editor.get("1.0", tk.END).strip()
        project_id = pr.project_id or self.config.get("default_project_id")
        base_branch = pr.selected_env_branch or "dev"
        new_branch = pr.feature_branch or f"PipelineCreateOrUpdate/{int(datetime.datetime.now().timestamp())}"
        mr_title = pr.pr_title or "MDIS YAML changes"
        mr_desc = pr.pr_desc or ""
        def do_mr():
            glh = GitLabHelper(self.config)
            if not GITLAB_AVAILABLE:
                messagebox.showerror("GitLab unavailable", "python-gitlab not installed on host.")
                return
            if not glh.gl:
                messagebox.showerror("Auth failed", "Not authenticated to GitLab. Set token in GitLab Profile.")
                return
            ok, result = glh.create_branch_and_commit_and_mr(project_id, new_branch, base_branch, files_dict, mr_title, mr_desc)
            if ok:
                messagebox.showinfo("MR created", f"Merge Request created: {result}")
                logger.info(f"MR created: {result}")
            else:
                messagebox.showerror("MR failed", f"Operation failed: {result}")
                logger.error(f"MR failed: {result}")
        t = threading.Thread(target=do_mr, daemon=True)
        t.start()

    def _update_status(self, txt):
        self.status_label.config(text=txt)

    def _load_config(self):
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
        return {}

    def _save_config(self):
        try:
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding='utf-8')
        except Exception:
            logger.exception("Failed to save config")

    def shutdown(self):
        self.config["font_family"] = self.font_family.get()
        self.config["font_size"] = self.font_size.get()
        self._save_config()
        logger.info("Shutting down")

# --- GitLab user dialog & PR dialog (kept compact) ---
class GitLabUserProfileDialog(tk.Toplevel):
    def __init__(self, master, config, app):
        super().__init__(master)
        self.title("GitLab User Profile")
        self.config = config
        self.app = app
        self.resizable(False, False)
        self._build()
    def _build(self):
        top = tk.Frame(self, bg="#5A287D", padx=10, pady=10)
        top.pack(fill="x")
        tk.Label(top, text="Please enter your Project Code and Private Token. Ensure the token has read*,write* and api access to the GitLab repository.", bg="#5A287D", fg="white", wraplength=420, justify="left").pack()
        body = tk.Frame(self, padx=10, pady=10)
        body.pack(fill="both")
        tk.Label(body, text="Project Code:").grid(row=0, column=0, sticky="w")
        self.project_code = tk.Entry(body, width=40); self.project_code.grid(row=0, column=1, pady=4)
        tk.Label(body, text="Access Token:").grid(row=1, column=0, sticky="w")
        self.token = tk.Entry(body, width=40, show="*"); self.token.grid(row=1, column=1, pady=4)
        tk.Label(body, text="User Name:").grid(row=2, column=0, sticky="w")
        self.user_name = tk.Entry(body, width=40, state='readonly'); self.user_name.grid(row=2, column=1, pady=4)
        tk.Label(body, text="User Id:").grid(row=3, column=0, sticky="w")
        self.user_id = tk.Entry(body, width=40, state='readonly'); self.user_id.grid(row=3, column=1, pady=4)
        tk.Label(body, text="Email Address:").grid(row=4, column=0, sticky="w")
        self.email = tk.Entry(body, width=40, state='readonly'); self.email.grid(row=4, column=1, pady=4)
        btns = tk.Frame(self, padx=10, pady=8); btns.pack(fill="x")
        self.test_btn = tk.Button(btns, text="Test", width=12, command=self.test_connection); self.test_btn.pack(side="left", padx=6)
        self.save_btn = tk.Button(btns, text="Save", width=12, command=self.save_settings, state='disabled'); self.save_btn.pack(side="left", padx=6)
        tk.Button(btns, text="Close", width=12, command=self.destroy).pack(side="right", padx=6)
        # load
        self.project_code.insert(0, self.config.get("default_project_id", ""))
        self.token.insert(0, self.config.get("gitlab_token", ""))

    def save_settings(self):
        self.config["gitlab_token"] = self.token.get().strip()
        self.config["default_project_id"] = self.project_code.get().strip()
        self.app._save_config()
        messagebox.showinfo("Saved", "GitLab settings saved")
        self.save_btn.config(state='disabled')

    def test_connection(self):
        project_code = self.project_code.get().strip()
        token = self.token.get().strip()
        if not project_code or not token:
            messagebox.showwarning("Missing", "Please enter Project Code and Access Token")
            return
        self.test_btn.config(state='disabled')
        def worker():
            try:
                if not GITLAB_AVAILABLE:
                    raise RuntimeError("python-gitlab not installed")
                url = self.config.get("gitlab_url", "https://gitlab.com")
                gl = gitlab.Gitlab(url, private_token=token)
                gl.auth()
                # fill UI
                current = None
                try:
                    current = gl.users.get(gl.user.id)
                except Exception:
                    try:
                        current = gl.user
                    except Exception:
                        current = None
                def fill():
                    if current:
                        self.user_name.config(state='normal'); self.user_name.delete(0, 'end'); self.user_name.insert(0, getattr(current, 'name', '')); self.user_name.config(state='readonly')
                        self.user_id.config(state='normal'); self.user_id.delete(0, 'end'); self.user_id.insert(0, str(getattr(current, 'id', ''))); self.user_id.config(state='readonly')
                        self.email.config(state='normal'); self.email.delete(0, 'end'); self.email.insert(0, getattr(current, 'email', '')); self.email.config(state='readonly')
                    self.save_btn.config(state='normal')
                    messagebox.showinfo("OK", "Connection successful")
                self.after(0, fill)
            except Exception as ex:
                logger.exception("GitLab test failed")
                def fail():
                    messagebox.showerror("GitLab Error", f"Failed to authenticate: {ex}")
                self.after(0, fail)
            finally:
                self.after(0, lambda: self.test_btn.config(state='normal'))
        threading.Thread(target=worker, daemon=True).start()

class PullRequestDialogTk(tk.Toplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.confirmed = False
        self.include_current_yaml = True
        self.project_id = app.config.get("default_project_id", "")
        self.feature_branch = None
        self.pr_title = None
        self.pr_desc = None
        self.selected_env_branch = None
        self._build()
    def _build(self):
        self.title("Create Merge Request")
        top = tk.Frame(self, bg="#5A287D", padx=10, pady=10); top.pack(fill="x")
        tk.Label(top, text="Please provide details for Merge Request", bg="#5A287D", fg="white").pack(anchor="w")
        body = tk.Frame(self, padx=10, pady=10); body.pack(fill="both", expand=True)
        tk.Label(body, text="Environment:").grid(row=0, column=0, sticky="w")
        self.env_cb = ttk.Combobox(body, values=["Dev","Test","AppDev","AppTest","Prod"], state='readonly'); self.env_cb.current(0); self.env_cb.grid(row=0,column=1,pady=4)
        tk.Label(body, text="Project ID (GitLab):").grid(row=1,column=0, sticky="w"); self.project_entry = tk.Entry(body); self.project_entry.grid(row=1,column=1, pady=4); self.project_entry.insert(0, self.project_id)
        tk.Label(body, text="PR Title:").grid(row=2,column=0, sticky="w"); self.pr_title_entry = tk.Entry(body, width=60); self.pr_title_entry.grid(row=2,column=1,pady=4); self.pr_title_entry.insert(0,"MDIS YAML changes")
        tk.Label(body, text="PR Description:").grid(row=3,column=0, sticky="nw"); self.pr_desc_text = scrolledtext.ScrolledText(body, height=6, width=50); self.pr_desc_text.grid(row=3,column=1,pady=4)
        btns = tk.Frame(self); btns.pack(fill="x", pady=8)
        tk.Button(btns, text="Cancel", command=self.cancel).pack(side="left", padx=6)
        tk.Button(btns, text="Create Merge Request", command=self.create_pr).pack(side="right", padx=6)
    def create_pr(self):
        yaml_text = self.app.editor.get("1.0", tk.END).strip()
        if not yaml_text:
            messagebox.showwarning("Empty YAML", "YAML content is empty. Please enter or open a YAML file before proceeding.")
            return
        if not self.project_entry.get().strip():
            messagebox.showwarning("Missing", "Please set Project ID")
            return
        self.selected_env_branch = self.env_cb.get().lower()
        spokes = FileService.get_tag_value(yaml_text, "spoke_name") or "spoke"
        pipeline = FileService.get_tag_value(yaml_text, "pipeline_id") or "pipeline"
        created_by = os.getlogin() if hasattr(os, "getlogin") else "user"
        self.feature_branch = f"PipelineCreateOrUpdate/{spokes}_{pipeline}_{created_by}_{int(datetime.datetime.now().timestamp())}"
        self.project_id = self.project_entry.get().strip()
        self.pr_title = self.pr_title_entry.get().strip()
        self.pr_desc = self.pr_desc_text.get("1.0", tk.END).strip()
        self.include_current_yaml = messagebox.askyesno("Include current YAML?", "Include the current editor YAML as part of the commit?")
        self.confirmed = True
        self.destroy()
    def cancel(self):
        self.confirmed = False; self.destroy()

# --- Entry point ---
def main():
    root = tk.Tk()
    app = App(root)
    def on_close():
        app.shutdown()
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()

if __name__ == "__main__":
    main()
