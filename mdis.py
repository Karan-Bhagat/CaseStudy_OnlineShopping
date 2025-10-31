#!/usr/bin/env python3
"""
mdis_yaml_validator_full_tk.py

Ported UI tweaks to better match the Java app layout and GitLab dialogs.
Single-file Tkinter application.

Notes:
 - Ensure optional libraries installed for full behavior:
    pip install ruamel.yaml pyyaml jsonschema python-gitlab
 - If icons are missing, the UI will use text buttons as fallback.
"""
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter.font as tkfont
from pathlib import Path
import json, os, sys, datetime, threading, traceback, re, webbrowser, logging
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

# --- Paths / config ---
HOME = Path.home()
CONFIG_PATH = HOME / ".mdis_yaml_validator_config.json"
LOG_DIR = HOME / ".mdis_yaml_validator_logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"mdis_validator_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# --- Logging ---
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

# GUI short log handler
class TextWidgetHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setLevel(logging.INFO)
    def emit(self, record):
        try:
            msg = f"[{record.levelname}] {record.getMessage()}\n"
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

# --- Services (File, Beautify, Validation) ---
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
        except Exception as e:
            logger.debug(f"get_tag_value error: {e}")
            return "Unknown"

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
                if not out.strip():
                    return "❌ Beautify failed (empty output)."
                return out.rstrip() + "\n"
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

class YamlValidationService:
    REQUIRED_FIELDS = ["pipeline_id", "template_id", "spoke_name"]
    @staticmethod
    def validate(yaml_content: str):
        try:
            template_id = FileService.get_tag_value(yaml_content, "template_id")
            if not template_id or template_id == "Unknown":
                # try parse whole doc
                if YAML_AVAILABLE:
                    ruamel_yaml = YAML()
                    parsed = ruamel_yaml.load(yaml_content)
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
                    if YAML_AVAILABLE:
                        ruamel_yaml = YAML()
                        data = ruamel_yaml.load(yaml_content)
                    else:
                        data = pyyaml.safe_load(yaml_content)
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
                                    ln = i
                                    break
                    except Exception:
                        ln = None
                    return False, f"❌ Schema validation failed: {ve.message}", ln
                except Exception as ex:
                    logger.exception("Error during schema validation")
                    return False, f"❌ Error during schema validation: {ex}", None

            # fallback structural checks
            try:
                if YAML_AVAILABLE:
                    ruamel_yaml = YAML()
                    data = ruamel_yaml.load(yaml_content)
                else:
                    data = pyyaml.safe_load(yaml_content)
            except Exception as e:
                logger.exception("YAML parse error")
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
                            ln = i
                            break
                    if ln:
                        break
                msg = f"❌ Missing required fields: {', '.join(missing)}"
                if ln:
                    msg += f"\nLikely at line {ln}"
                return False, msg, ln
            return True, f"✅ YAML is valid (structural checks passed)\nTemplate: {FileService.get_tag_value(yaml_content,'template_id')}", None
        except Exception as e:
            logger.exception("Validation error")
            return False, f"❌ Validation error: {e}", None

# --- GitLab helper (optional) ---
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

    # create MR simplified helper - same as original (attempt create/update commit & MR)
    def create_branch_and_commit_and_mr(self, project_id, branch_name, base_branch, files_dict, mr_title, mr_desc):
        if not GITLAB_AVAILABLE:
            return False, "python-gitlab not installed on this host"
        if not self.gl:
            return False, "Not authenticated to GitLab (missing/invalid token)"
        try:
            project = self.gl.projects.get(project_id)
        except Exception as e:
            return False, f"Failed to open project {project_id}: {e}"
        try:
            project.branches.create({'branch': branch_name, 'ref': base_branch})
            logger.info(f"Created branch {branch_name} from {base_branch}")
        except Exception:
            logger.info("Branch may already exist; continuing")
        actions = []
        for path_in_repo, content in files_dict.items():
            actions.append({'action': 'create', 'file_path': path_in_repo, 'content': content})
        try:
            commit_data = {'branch': branch_name, 'commit_message': f"Add files for MR: {mr_title}", 'actions': actions}
            project.commits.create(commit_data)
            logger.info(f"Committed {len(actions)} files to {branch_name}")
        except Exception:
            # try update if create fails
            actions = []
            for path_in_repo, content in files_dict.items():
                actions.append({'action': 'update', 'file_path': path_in_repo, 'content': content})
            commit_data = {'branch': branch_name, 'commit_message': f"Update files for MR: {mr_title}", 'actions': actions}
            project.commits.create(commit_data)
            logger.info("Committed updates to existing files")
        try:
            mr = project.mergerequests.create({'source_branch': branch_name, 'target_branch': base_branch, 'title': mr_title, 'description': mr_desc})
            logger.info(f"Created MR: {mr.web_url}")
            return True, mr.web_url
        except Exception as e:
            return False, f"Failed to create MR: {e}"

# --- Main Application ---
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("MDIS- YAML Editor + Validator")
        self.root.geometry("1200x760")
        self.config = self._load_config()
        self.current_path = None
        self.font_family = tk.StringVar(value=self.config.get("font_family", "Consolas"))
        self.font_size = tk.IntVar(value=self.config.get("font_size", 11))
        self.theme = tk.StringVar(value=self.config.get("theme", "light"))

        # top banner (purple) to mimic Java header
        self._build_banner()

        # build menubar (File, Format, GitLab, Themes, Help)
        self._build_menu()

        # main area: left vertical toolbar, editor center, right tabs
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill="both", expand=True)

        left_toolbar_frame = tk.Frame(main_frame, width=64, bg="#ffffff")
        left_toolbar_frame.pack(side="left", fill="y")

        editor_and_tabs = tk.Frame(main_frame)
        editor_and_tabs.pack(side="left", fill="both", expand=True)

        # vertical toolbar (stacked)
        self._build_vertical_toolbar(left_toolbar_frame)

        # editor area with gutter
        gutter_frame = tk.Frame(editor_and_tabs)
        gutter_frame.pack(fill="both", expand=True)
        self.line_numbers = tk.Text(gutter_frame, width=6, padx=4, takefocus=0, border=0, background="#f0f0f0", state='disabled')
        self.line_numbers.pack(side="left", fill="y")
        self.text = scrolledtext.ScrolledText(gutter_frame, wrap=tk.NONE)
        self.text.pack(side="left", fill="both", expand=True)
        # sync scroll
        self.text['yscrollcommand'] = self._on_text_scroll
        self.text.bind("<<Modified>>", self._on_text_changed)
        self.text.bind("<KeyRelease>", self._on_text_changed)

        self._apply_font()

        # bottom status + log and GitLab tab on right
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill="x")
        self.status = tk.Label(bottom_frame, text="Ready", anchor="w")
        self.status.pack(fill="x")

        # Right-side tabs (log, git)
        right_panel = tk.Frame(self.root, width=360)
        right_panel.pack(side="right", fill="y")
        self.tabs = ttk.Notebook(right_panel)
        self.tabs.pack(fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(self.tabs, height=12, state='disabled')
        self.tabs.add(self.log_text, text="Log")
        self.text_handler = TextWidgetHandler(self.log_text)
        self.text_handler.setFormatter(fh_formatter)
        logger.addHandler(self.text_handler)

        # GitLab quick tab (info + button)
        git_frame = tk.Frame(self.tabs)
        self.tabs.add(git_frame, text="GitLab")
        self.git_info = tk.Label(git_frame, text=self._git_status_text(), justify="left")
        self.git_info.pack(anchor="nw", padx=6, pady=8)
        tk.Button(git_frame, text="GitLab Profile", command=self.open_gitlab_user_dialog).pack(anchor="nw", padx=6, pady=4)
        tk.Button(git_frame, text="Create MR", command=self._create_mr_flow).pack(anchor="nw", padx=6, pady=2)

        logger.info("MDIS YAML Validator started (Tk port)")

        self._update_line_numbers()

    def _build_banner(self):
        # purple header like Java app
        banner = tk.Frame(self.root, height=96, bg="#5A287D")
        banner.pack(fill="x")
        # left: logo text
        logo = tk.Label(banner, text="NatWest Group", fg="white", bg="#5A287D", font=("Segoe UI", 18, "bold"))
        logo.pack(side="left", padx=18, pady=20)
        title = tk.Label(banner, text="MDIS - Yaml Editor + Validator", fg="white", bg="#5A287D", font=("Segoe UI", 20, "bold"))
        title.pack(side="right", padx=18)

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        filem = tk.Menu(menubar, tearoff=0)
        filem.add_command(label="Open", command=self.open_file)
        filem.add_command(label="Save", command=self.save_file)
        filem.add_command(label="Save As...", command=self.save_as_file)
        filem.add_separator()
        filem.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filem)

        formatm = tk.Menu(menubar, tearoff=0)
        formatm.add_command(label="Beautify", command=self.beautify_yaml)
        formatm.add_command(label="Validate", command=self.validate_yaml)
        formatm.add_command(label="Font...", command=self.font_chooser)
        menubar.add_cascade(label="Format", menu=formatm)

        gitm = tk.Menu(menubar, tearoff=0)
        gitm.add_command(label="My Gitlab Profile", command=self.open_gitlab_user_dialog)
        gitm.add_command(label="Create Pull Request", command=self._create_mr_flow)
        menubar.add_cascade(label="GitLab", menu=gitm)

        themem = tk.Menu(menubar, tearoff=0)
        themem.add_radiobutton(label="Light", variable=self.theme, value="light", command=self._apply_theme)
        themem.add_radiobutton(label="Dark", variable=self.theme, value="dark", command=self._apply_theme)
        menubar.add_cascade(label="Themes", menu=themem)

        helpm = tk.Menu(menubar, tearoff=0)
        helpm.add_command(label="Readme / Help", command=self.show_help)
        helpm.add_command(label="Open docs (web)", command=lambda: webbrowser.open("https://example.com"))
        helpm.add_separator()
        helpm.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=helpm)

        self.root.config(menu=menubar)

    def _build_vertical_toolbar(self, parent):
        # recreate Java vertical toolbar: open/save/beautify/validate/font/createPR/profile/help
        # If you have icons folder, replace text Buttons with Image-based Buttons
        b_open = tk.Button(parent, text="Open\n(O)", width=8, command=self.open_file)
        b_open.pack(pady=6)
        b_save = tk.Button(parent, text="Save\n(S)", width=8, command=self.save_file)
        b_save.pack(pady=6)
        b_saveas = tk.Button(parent, text="Save As", width=8, command=self.save_as_file)
        b_saveas.pack(pady=6)
        tk.Frame(parent, height=6, bg="#ffffff").pack()
        b_beaut = tk.Button(parent, text="Beautify", width=8, command=self.beautify_yaml)
        b_beaut.pack(pady=6)
        b_valid = tk.Button(parent, text="Validate", width=8, command=self.validate_yaml)
        b_valid.pack(pady=6)
        b_clear = tk.Button(parent, text="Clear", width=8, command=self.clear_editor)
        b_clear.pack(pady=6)
        tk.Frame(parent, height=6, bg="#ffffff").pack()
        b_font = tk.Button(parent, text="Font", width=8, command=self.font_chooser)
        b_font.pack(pady=6)
        tk.Frame(parent, height=6, bg="#ffffff").pack()
        b_pr = tk.Button(parent, text="Create\nPR", width=8, command=self._create_mr_flow)
        b_pr.pack(pady=6)
        b_profile = tk.Button(parent, text="Profile", width=8, command=self.open_gitlab_user_dialog)
        b_profile.pack(pady=6)
        tk.Frame(parent, height=6, bg="#ffffff").pack()
        b_help = tk.Button(parent, text="Help", width=8, command=self.show_help)
        b_help.pack(pady=6)

    # --- File / Editor actions ---
    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[("YAML files","*.yaml *.yml"),("All files","*.*")])
        if not path:
            return
        try:
            content = Path(path).read_text(encoding='utf-8')
            self.text.config(state='normal')
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, content)
            self.current_path = path
            logger.info(f"Opened file {path}")
            self.status.config(text=f"Opened: {os.path.basename(path)}")
            self._update_line_numbers()
        except Exception as e:
            logger.exception("Failed to open file")
            messagebox.showerror("Open error", f"Failed to open file: {e}")

    def save_file(self):
        if not self.current_path:
            return self.save_as_file()
        try:
            Path(self.current_path).write_text(self.text.get("1.0", tk.END), encoding='utf-8')
            logger.info(f"Saved file {self.current_path}")
            self.status.config(text=f"Saved: {os.path.basename(self.current_path)}")
            messagebox.showinfo("Saved", f"Saved: {self.current_path}")
        except Exception as e:
            logger.exception("Save failed")
            messagebox.showerror("Save error", f"Failed to save file: {e}")

    def save_as_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".yaml", filetypes=[("YAML files","*.yaml"),("All files","*.*")])
        if not path:
            return
        try:
            Path(path).write_text(self.text.get("1.0", tk.END), encoding='utf-8')
            self.current_path = path
            logger.info(f"Saved As {path}")
            self.status.config(text=f"Saved: {os.path.basename(path)}")
            messagebox.showinfo("Saved", f"Saved: {path}")
        except Exception as e:
            logger.exception("Save as failed")
            messagebox.showerror("Save as error", f"Failed to save file: {e}")

    def beautify_yaml(self):
        content = self.text.get("1.0", tk.END).rstrip()
        if not content:
            messagebox.showwarning("Empty", "Open or paste YAML first")
            return
        formatted = BeautifyService.beautify(content)
        if isinstance(formatted, str) and formatted.startswith("❌"):
            logger.error(f"Beautify failed: {formatted}")
            messagebox.showerror("Beautify error", formatted)
            self.status.config(text="Beautify failed")
            return
        self.text.config(state='normal')
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, formatted)
        logger.info("Beautified YAML")
        self.status.config(text="Beautified YAML")
        self._update_line_numbers()

    def validate_yaml(self):
        content = self.text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Empty", "Open or paste YAML first")
            return False
        ok, msg, ln = YamlValidationService.validate(content)
        logger.info("Validation: " + (msg.splitlines()[0] if msg else "finished"))
        self.status.config(text=(msg.splitlines()[0] if msg else "Validation finished"))
        if ok:
            messagebox.showinfo("Validation", msg)
            return True
        else:
            if ln:
                try:
                    self.text.config(state='normal')
                    line_start = f"{ln}.0"
                    line_end = f"{ln}.end"
                    self.text.tag_remove("errline", "1.0", tk.END)
                    self.text.tag_add("errline", line_start, line_end)
                    self.text.tag_config("errline", background="#ffdddd")
                    self.text.see(line_start)
                except Exception:
                    pass
            messagebox.showerror("Validation", msg)
            return False

    def clear_editor(self):
        current = self.text.get("1.0", tk.END)
        if not current.strip():
            self.current_path = None
            self.status.config(text="Cleared")
            return
        if messagebox.askokcancel("Clear editor", "Are you sure you want to clear the editor contents? This cannot be undone."):
            try:
                self.text.delete("1.0", tk.END)
                self.current_path = None
                self.status.config(text="Cleared")
                logger.info("Editor cleared by user")
                self._update_line_numbers()
            except Exception as e:
                logger.exception("Failed to clear editor")
                messagebox.showerror("Clear failed", f"Failed to clear editor: {e}")

    # --- helpers / UI ---
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
        size_spin.delete(0, "end")
        size_spin.insert(0, str(self.font_size.get()))
        size_spin.grid(row=1, column=1, padx=6, pady=6)
        def apply_font():
            self.font_family.set(fam_cb.get())
            try:
                self.font_size.set(int(size_spin.get()))
            except Exception:
                self.font_size.set(11)
            self._apply_font()
            self.config["font_family"] = self.font_family.get()
            self.config["font_size"] = self.font_size.get()
            self._save_config()
            chooser.destroy()
            logger.info(f"Font changed to {self.font_family.get()} {self.font_size.get()}")
        tk.Button(chooser, text="Apply", command=apply_font).grid(row=2, column=0, columnspan=2, pady=8)

    def _apply_font(self):
        f = (self.font_family.get(), self.font_size.get())
        try:
            self.text.configure(font=f)
            ln_font = (self.font_family.get(), max(8, self.font_size.get()-1))
            self.line_numbers.configure(font=ln_font)
        except Exception:
            self.text.configure(font=("Consolas", 11))

    def _apply_theme(self):
        t = self.theme.get()
        if t == "dark":
            bg = "#1e1e1e"; fg = "#dcdcdc"; edit_bg = "#252526"
        else:
            bg = "#f0f0f0"; fg = "#000000"; edit_bg = "#ffffff"
        try:
            self.root.configure(bg=bg)
        except Exception:
            pass
        self.text.configure(bg=edit_bg, fg=fg, insertbackground=fg)
        self.log_text.configure(bg=edit_bg, fg=fg)
        self.status.configure(bg=bg, fg=fg)
        self.line_numbers.configure(bg=edit_bg, fg=fg)
        self.config["theme"] = t
        self._save_config()
        logger.info(f"Theme set to {t}")

    def _load_config(self):
        try:
            if CONFIG_PATH.exists():
                return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except Exception:
            logger.exception("Failed to load config")
        return {}

    def _save_config(self):
        try:
            CONFIG_PATH.write_text(json.dumps(self.config, indent=2), encoding='utf-8')
        except Exception:
            logger.exception("Failed to save config")

    def _git_status_text(self):
        if not GITLAB_AVAILABLE:
            return "python-gitlab not installed — GitLab integration disabled. Install python-gitlab to enable."
        token = self.config.get("gitlab_token")
        if not token:
            return "GitLab available but token not set (GitLab -> My Gitlab Profile)"
        return "GitLab available (token configured)."

    def open_gitlab_user_dialog(self):
        dlg = GitLabUserProfileDialog(self.root, self.config, self)
        dlg.grab_set()

    def _attach_current_yaml(self):
        content = self.text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Empty", "No YAML in editor to attach")
            return
        fname = "manifest.yaml"
        if self.current_path:
            fname = Path(self.current_path).name
        target_path = f"mdis_manifests/{fname}"
        attachments = self.config.get("_attachments", {})
        attachments[target_path] = content
        self.config["_attachments"] = attachments
        self._save_config()
        messagebox.showinfo("Attached", f"Attached as {target_path} (will be committed when you create MR)")

    # --- Pull request / MR flow (mimic Java behavior) ---
    def _create_mr_flow(self):
        logger.info("Creation of Pull Request Validation Initiated")
        yaml_text = self.text.get("1.0", tk.END)
        if yaml_text is None or yaml_text.strip() == "":
            logger.warning("YAML content is empty, aborting validation and Pull Request")
            messagebox.showwarning("Empty YAML", "YAML content is empty. Please enter or open a YAML file before proceeding.")
            return
        # validate and open PR dialog (similar to Java)
        if not self.validate_yaml():
            logger.severe("YAML validation failed. Please fix errors before proceeding.")
            messagebox.showerror("Validation Error", "YAML validation failed. Please fix errors before proceeding.")
            return
        pr = PullRequestDialogTk(self.root, self)
        pr.wait_window()
        if not pr.confirmed:
            return
        # prepare commit contents and call GitLabHelper in thread
        attachments = self.config.get("_attachments", {})
        files_dict = dict(attachments)
        include_current = pr.include_current_yaml
        if include_current:
            fname = Path(self.current_path).name if self.current_path else "pasted.yaml"
            files_dict[f"mdis_manifests/{fname}"] = self.text.get("1.0", tk.END).strip()
        project_id = pr.project_id or self.config.get("default_project_id")
        base_branch = pr.selected_env_branch or "dev"
        new_branch = pr.feature_branch or f"PipelineCreateOrUpdate/{int(datetime.datetime.now().timestamp())}"
        mr_title = pr.pr_title or "MDIS YAML changes"
        mr_desc = pr.pr_desc or ""
        logger.info("Preparing to create MR...")
        def do_mr():
            glh = GitLabHelper(self.config)
            if not GITLAB_AVAILABLE:
                messagebox.showerror("GitLab unavailable", "python-gitlab library is not installed on this host.\nInstall it to enable MR creation.")
                return
            if not glh.gl:
                messagebox.showerror("Auth failed", "Not authenticated to GitLab. Set token in GitLab settings.")
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

    def show_help(self):
        deps = []
        deps.append("ruamel.yaml" if YAML_AVAILABLE else "ruamel.yaml (missing)")
        deps.append("PyYAML" if PYYAML_AVAILABLE else "PyYAML (missing)")
        deps.append("jsonschema" if JSONSCHEMA_AVAILABLE else "jsonschema (missing)")
        deps.append("python-gitlab" if GITLAB_AVAILABLE else "python-gitlab (missing)")
        msg = (
            "MDIS YAML Validator - Help\n\n"
            "Core actions:\n"
            " - Open: open a YAML file\n"
            " - Beautify: format using ruamel.yaml (if present) or PyYAML\n"
            " - Validate: schema-first if ./schema/{template_id}.json exists and jsonschema installed; otherwise fallback structural checks\n"
            " - Save / Save As: save file\n\n"
            f"Detected libs: {', '.join(deps)}\n\n"
            "To enable GitLab MR creation: install python-gitlab and set your private token (GitLab -> My Gitlab Profile).\n"
        )
        messagebox.showinfo("Help", msg)

    def show_about(self):
        messagebox.showinfo("About", "MDIS YAML Validator\nPorted features from Java app into Tkinter.\n")

    def shutdown(self):
        logger.info("Shutting down")
        self.config["font_family"] = self.font_family.get()
        self.config["font_size"] = self.font_size.get()
        self.config["theme"] = self.theme.get()
        self._save_config()

    # --- Line numbers ---
    def _update_line_numbers(self, *args):
        try:
            self.line_numbers.configure(state='normal')
            self.line_numbers.delete("1.0", tk.END)
            total_lines = int(self.text.index('end-1c').split('.')[0])
            lines = "\n".join(str(i) for i in range(1, total_lines+1))
            self.line_numbers.insert(tk.END, lines)
            self.line_numbers.configure(state='disabled')
        except Exception:
            pass
        try:
            self.text.edit_modified(False)
        except Exception:
            pass

    def _on_text_changed(self, event=None):
        self._update_line_numbers()

    def _on_text_scroll(self, *args):
        try:
            self.text.yview_moveto(args[0])
            self.line_numbers.yview_moveto(args[0])
        except Exception:
            pass

# --- GitLab User Profile Dialog (Tk version) ---
class GitLabUserProfileDialog(tk.Toplevel):
    def __init__(self, master, config, app):
        super().__init__(master)
        self.title("GitLab User Profile")
        self.config = config
        self.app = app
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.build_ui()
        self.load_settings()
        self.transient(master)
        self.grab_set()
        self.focus()

    def build_ui(self):
        top_frame = tk.Frame(self, bg="#5A287D", padx=12, pady=12)
        top_frame.pack(fill="x")
        lbl_icon = tk.Label(top_frame, text="", bg="#5A287D", fg="white", font=("Segoe UI", 24))
        lbl_icon.pack(side="left")
        msg = "Please enter your Project Code and Private Token. Ensure the token has read*,write* and api access to the GitLab repository."
        lbl_msg = tk.Label(top_frame, text=msg, bg="#5A287D", fg="white", justify="left", wraplength=380)
        lbl_msg.pack(side="left", padx=12)

        form = tk.Frame(self, padx=12, pady=12)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Project Code:").grid(row=0, column=0, sticky="w")
        self.project_code = tk.Entry(form, width=40)
        self.project_code.grid(row=0, column=1, pady=4)

        tk.Label(form, text="Access Token:").grid(row=1, column=0, sticky="w")
        self.token = tk.Entry(form, width=40, show="*")
        self.token.grid(row=1, column=1, pady=4)

        tk.Label(form, text="User Name:").grid(row=2, column=0, sticky="w")
        self.user_name = tk.Entry(form, width=40, state='readonly')
        self.user_name.grid(row=2, column=1, pady=4)

        tk.Label(form, text="User Id:").grid(row=3, column=0, sticky="w")
        self.user_id = tk.Entry(form, width=40, state='readonly')
        self.user_id.grid(row=3, column=1, pady=4)

        tk.Label(form, text="Email Address:").grid(row=4, column=0, sticky="w")
        self.email = tk.Entry(form, width=40, state='readonly')
        self.email.grid(row=4, column=1, pady=4)

        status_frame = tk.Frame(self, padx=12, pady=8)
        status_frame.pack(fill="x")
        self.status_label = tk.Label(status_frame, text="", fg="green")
        self.status_label.pack(side="left")

        btn_frame = tk.Frame(self, padx=12, pady=8)
        btn_frame.pack(fill="x")
        self.test_btn = tk.Button(btn_frame, text="Test", width=12, command=self.test_connection)
        self.test_btn.pack(side="left", padx=6)
        self.save_btn = tk.Button(btn_frame, text="Save", width=12, command=self.save_settings, state='disabled')
        self.save_btn.pack(side="left", padx=6)
        self.close_btn = tk.Button(btn_frame, text="Close", width=12, command=self.close)
        self.close_btn.pack(side="right", padx=6)

    def load_settings(self):
        self.project_code.delete(0, tk.END)
        self.project_code.insert(0, self.config.get("default_project_id", ""))
        self.token.delete(0, tk.END)
        self.token.insert(0, self.config.get("gitlab_token", ""))

    def save_settings(self):
        self.config["gitlab_url"] = self.config.get("gitlab_url", "https://gitlab.com")
        self.config["gitlab_token"] = self.token.get().strip()
        self.config["default_project_id"] = self.project_code.get().strip()
        self.app._save_config()
        self.app.git_info.config(text=self.app._git_status_text())
        messagebox.showinfo("Saved", "GitLab settings saved locally")
        logger.info("GitLab settings updated")
        self.save_btn.config(state='disabled')

    def test_connection(self):
        project_code = self.project_code.get().strip()
        token = self.token.get().strip()
        if not project_code:
            messagebox.showwarning("Input Required", "Please provide Project Code.")
            return
        if not token:
            messagebox.showwarning("Input Required", "Please provide Access Token.")
            return
        # disable UI and run test in background
        self.test_btn.config(state='disabled')
        self.status_label.config(text="Verifying...", fg="black")
        def worker():
            try:
                if not GITLAB_AVAILABLE:
                    raise RuntimeError("python-gitlab not installed")
                url = self.config.get("gitlab_url", "https://gitlab.com")
                gl = gitlab.Gitlab(url, private_token=token)
                gl.auth()
                u = gl.users.get(gl.user.id) if hasattr(gl, 'user') else gl.user
                # fetch current user explicitly
                try:
                    current = gl.user
                except Exception:
                    try:
                        current = gl.users.get(gl.user.id)
                    except Exception:
                        current = None
                # fill into UI (on main thread)
                def on_ok():
                    self.user_name.config(state='normal'); self.user_name.delete(0, tk.END)
                    self.user_name.insert(0, getattr(gl, 'user', getattr(gl, 'current_user', "")) if False else getattr(current, 'name', ''))
                    self.user_name.config(state='readonly')
                    self.user_id.config(state='normal'); self.user_id.delete(0, tk.END)
                    self.user_id.insert(0, str(getattr(current, 'username', getattr(current, 'id', ''))))
                    self.user_id.config(state='readonly')
                    self.email.config(state='normal'); self.email.delete(0, tk.END)
                    self.email.insert(0, getattr(current, 'email', ''))
                    self.email.config(state='readonly')
                    self.status_label.config(text="Connection Successful", fg="green")
                    self.save_btn.config(state='normal')
                    self.app.config["gitlab_token"] = token
                    self.app.config["default_project_id"] = project_code
                    self.app._save_config()
                    self.app.git_info.config(text=self.app._git_status_text())
                self.after(0, on_ok)
            except Exception as ex:
                logger.exception("GitLab test failed")
                def on_fail():
                    messagebox.showerror("GitLab Error", f"Failed to authenticate: {ex}")
                    self.status_label.config(text="Connection failed", fg="red")
                    self.save_btn.config(state='disabled')
                self.after(0, on_fail)
            finally:
                def reenable():
                    self.test_btn.config(state='normal')
                self.after(0, reenable)
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def close(self):
        self.destroy()

# --- Pull Request Dialog (Tk) ---
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
        self.setup_ui()
        self.transient(master)
        self.grab_set()
        self.focus()

    def setup_ui(self):
        self.title("Create Merge Request")
        self.geometry("700x460")
        top = tk.Frame(self, bg="#5A287D", padx=10, pady=10)
        top.pack(fill="x")
        lbl_icon = tk.Label(top, text="", bg="#5A287D", fg="white", font=("Segoe UI", 20))
        lbl_icon.pack(side="left")
        msg = "Please provide the necessary files (Yaml and SQL) to create a GitLab Merge Request.\nMCR is required for production deployments only."
        tk.Label(top, text=msg, bg="#5A287D", fg="white", wraplength=540, justify="left").pack(side="left", padx=8)

        body = tk.Frame(self, padx=12, pady=12)
        body.pack(fill="both", expand=True)

        tk.Label(body, text="Environment:").grid(row=0, column=0, sticky="w")
        self.env_cb = ttk.Combobox(body, values=["Dev", "Test", "AppDev", "AppTest", "Prod"], state='readonly')
        self.env_cb.current(0)
        self.env_cb.grid(row=0, column=1, sticky="w", pady=4)
        tk.Label(body, text="MCR / TCR:").grid(row=0, column=2, sticky="w")
        self.mcr_entry = tk.Entry(body)
        self.mcr_entry.grid(row=0, column=3, sticky="w", padx=6)

        tk.Label(body, text="Pipeline Config File:").grid(row=1, column=0, sticky="w")
        self.pipeline_file = tk.Entry(body, width=60)
        self.pipeline_file.grid(row=1, column=1, columnspan=3, sticky="w", pady=6)
        if self.app.current_path:
            self.pipeline_file.insert(0, self.app.current_path)
        tk.Button(body, text="Browse...", command=self.browse_pipeline).grid(row=1, column=4, padx=6)

        tk.Label(body, text="Manifest Config File:").grid(row=2, column=0, sticky="w")
        self.settings_file = tk.Entry(body, width=60)
        self.settings_file.grid(row=2, column=1, columnspan=3, sticky="w", pady=6)
        tk.Button(body, text="Select...", command=self.browse_manifest).grid(row=2, column=4, padx=6)

        tk.Label(body, text="SQL Files (optional):").grid(row=3, column=0, sticky="nw")
        self.sql_listbox = tk.Listbox(body, height=6, width=60)
        self.sql_listbox.grid(row=3, column=1, columnspan=3, sticky="w", pady=6)
        tk.Button(body, text="Add SQL", command=self.add_sql).grid(row=3, column=4, padx=6, sticky="n")
        tk.Button(body, text="Remove", command=self.remove_sql).grid(row=3, column=4, padx=6, sticky="s")

        tk.Label(body, text="Project ID (GitLab):").grid(row=4, column=0, sticky="w")
        self.project_entry = tk.Entry(body)
        self.project_entry.grid(row=4, column=1, sticky="w")
        self.project_entry.insert(0, self.project_id)

        tk.Label(body, text="PR Title:").grid(row=5, column=0, sticky="w")
        self.pr_title_entry = tk.Entry(body, width=60)
        self.pr_title_entry.grid(row=5, column=1, columnspan=3, sticky="w", pady=6)
        self.pr_title_entry.insert(0, "MDIS YAML changes")

        tk.Label(body, text="PR Description:").grid(row=6, column=0, sticky="nw")
        self.pr_desc_text = scrolledtext.ScrolledText(body, height=6, width=60)
        self.pr_desc_text.grid(row=6, column=1, columnspan=3, pady=6)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill="x", pady=8)
        self.create_btn = tk.Button(btn_frame, text="Create Merge Request", command=self.create_pr, state='normal')
        self.create_btn.pack(side="right", padx=8)
        tk.Button(btn_frame, text="Cancel", command=self.cancel).pack(side="right")

    def browse_pipeline(self):
        p = filedialog.askopenfilename(filetypes=[("YAML files","*.yaml *.yml"),("All files","*.*")])
        if p:
            self.pipeline_file.delete(0, tk.END)
            self.pipeline_file.insert(0, p)

    def browse_manifest(self):
        p = filedialog.askopenfilename(filetypes=[("YAML files","*.yaml *.yml"),("All files","*.*")])
        if p:
            self.settings_file.delete(0, tk.END)
            self.settings_file.insert(0, p)

    def add_sql(self):
        files = filedialog.askopenfilenames(filetypes=[("SQL files","*.sql"),("All files","*.*")])
        for f in files:
            self.sql_listbox.insert(tk.END, f)

    def remove_sql(self):
        sel = list(self.sql_listbox.curselection())
        for i in reversed(sel):
            self.sql_listbox.delete(i)

    def create_pr(self):
        # basic checks like Java: YAML present, project id, feature branch name later created by backend
        yaml_text = self.app.text.get("1.0", tk.END).strip()
        if not yaml_text:
            messagebox.showwarning("Empty YAML", "YAML content is empty. Please enter or open a YAML file before proceeding.")
            return
        if not self.project_entry.get().strip():
            messagebox.showwarning("Missing", "Please set Project ID")
            return
        # gather attributes
        self.selected_env_branch = self.env_cb.get().lower()
        # set selected env mapping (dev/test/prod mapping similar Java)
        env = self.selected_env_branch
        spokes = FileService.get_tag_value(yaml_text, "spoke_name") or "spoke"
        pipeline = FileService.get_tag_value(yaml_text, "pipeline_id") or "pipeline"
        created_by = os.getlogin() if hasattr(os, 'getlogin') else "user"
        self.feature_branch = f"PipelineCreateOrUpdate/{spokes}_{pipeline}_{created_by}_{int(datetime.datetime.now().timestamp())}"
        self.project_id = self.project_entry.get().strip()
        self.pr_title = self.pr_title_entry.get().strip()
        self.pr_desc = self.pr_desc_text.get("1.0", tk.END).strip()
        # include current yaml?
        self.include_current_yaml = messagebox.askyesno("Include current YAML?", "Include the current editor YAML as part of the commit?")
        self.confirmed = True
        self.destroy()

    def cancel(self):
        self.confirmed = False
        self.destroy()

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
