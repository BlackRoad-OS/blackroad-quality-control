#!/usr/bin/env python3
"""BlackRoad Quality Control - Checklist and defect tracker."""
from __future__ import annotations
import argparse, json, sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

GREEN = "\033[0;32m"; RED = "\033[0;31m"; YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"; BLUE = "\033[0;34m"; BOLD = "\033[1m"; NC = "\033[0m"
DB_PATH = Path.home() / ".blackroad" / "quality_control.db"


@dataclass
class ChecklistItem:
    id: Optional[int]; title: str; category: str; severity: str
    status: str = "pending"; notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class Defect:
    id: Optional[int]; title: str; description: str; severity: str; component: str
    status: str = "open"; assignee: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None


class QualityControlDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS checklist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                category TEXT NOT NULL, severity TEXT NOT NULL,
                status TEXT DEFAULT 'pending', notes TEXT DEFAULT '',
                created_at TEXT, updated_at TEXT)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS defects (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                description TEXT NOT NULL, severity TEXT NOT NULL,
                component TEXT NOT NULL, status TEXT DEFAULT 'open',
                assignee TEXT DEFAULT '', created_at TEXT, resolved_at TEXT)""")
            conn.commit()

    def add_checklist_item(self, item: ChecklistItem) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO checklist_items (title,category,severity,status,notes,created_at,updated_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (item.title, item.category, item.severity, item.status,
                 item.notes, item.created_at, item.updated_at))
            conn.commit(); return cur.lastrowid

    def add_defect(self, defect: Defect) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "INSERT INTO defects (title,description,severity,component,status,assignee,created_at,resolved_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (defect.title, defect.description, defect.severity, defect.component,
                 defect.status, defect.assignee, defect.created_at, defect.resolved_at))
            conn.commit(); return cur.lastrowid

    def update_checklist_status(self, item_id: int, status: str, notes: str = "") -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE checklist_items SET status=?,notes=?,updated_at=? WHERE id=?",
                         (status, notes, datetime.now().isoformat(), item_id))
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0

    def resolve_defect(self, defect_id: int) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE defects SET status='resolved',resolved_at=? WHERE id=?",
                         (datetime.now().isoformat(), defect_id))
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0] > 0

    def list_checklist_items(self, category: Optional[str] = None) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            q, p = "SELECT * FROM checklist_items", ()
            if category:
                q += " WHERE category=?"; p = (category,)
            return [dict(r) for r in conn.execute(q + " ORDER BY created_at DESC", p).fetchall()]

    def list_defects(self, status: Optional[str] = None) -> list:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            q, p = "SELECT * FROM defects", ()
            if status:
                q += " WHERE status=?"; p = (status,)
            return [dict(r) for r in conn.execute(q + " ORDER BY created_at DESC", p).fetchall()]

    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cl = {r[0]: r[1] for r in conn.execute(
                "SELECT status,COUNT(*) FROM checklist_items GROUP BY status")}
            df = {r[0]: r[1] for r in conn.execute(
                "SELECT severity,COUNT(*) FROM defects WHERE status='open' GROUP BY severity")}
            return {"checklist": cl, "open_defects_by_severity": df}

    def export_json(self) -> str:
        return json.dumps({"checklist_items": self.list_checklist_items(),
                           "defects": self.list_defects(), "stats": self.get_stats(),
                           "exported_at": datetime.now().isoformat()}, indent=2)


def _sev(s): return {"critical": RED, "high": "\033[0;91m", "medium": YELLOW, "low": GREEN}.get(s, NC)
def _st(s): return {"passed": GREEN, "failed": RED, "open": RED, "resolved": GREEN,
                    "closed": CYAN, "pending": YELLOW, "in_progress": BLUE}.get(s, NC)


def cmd_list(args, db):
    if args.type == "checklist":
        items = db.list_checklist_items(getattr(args, "category", None))
        print(f"\n{BOLD}{CYAN}{'ID':<5} {'Title':<35} {'Category':<15} {'Severity':<10} {'Status'}{NC}")
        print("-" * 78)
        for i in items:
            print(f"{i['id']:<5} {i['title'][:34]:<35} {i['category']:<15} "
                  f"{_sev(i['severity'])}{i['severity']:<10}{NC} {_st(i['status'])}{i['status']}{NC}")
        print(f"\n{CYAN}Total: {len(items)}{NC}\n")
    else:
        defects = db.list_defects(getattr(args, "filter_status", None))
        print(f"\n{BOLD}{CYAN}{'ID':<5} {'Title':<30} {'Component':<15} {'Severity':<10} {'Status':<12} {'Assignee'}{NC}")
        print("-" * 90)
        for d in defects:
            print(f"{d['id']:<5} {d['title'][:29]:<30} {d['component']:<15} "
                  f"{_sev(d['severity'])}{d['severity']:<10}{NC} {_st(d['status'])}{d['status']:<12}{NC} {d['assignee']}")
        print(f"\n{CYAN}Total: {len(defects)}{NC}\n")


def cmd_add(args, db):
    if args.type == "checklist":
        iid = db.add_checklist_item(ChecklistItem(
            id=None, title=args.title, category=args.category, severity=args.severity))
        print(f"{GREEN}Added checklist item #{iid}: {args.title}{NC}")
    else:
        did = db.add_defect(Defect(id=None, title=args.title, description=args.description,
                                   severity=args.severity, component=args.component,
                                   assignee=args.assignee))
        print(f"{RED}Logged defect #{did}: {args.title}{NC}")


def cmd_status(args, db):
    stats = db.get_stats()
    print(f"\n{BOLD}{CYAN}=== Quality Control Dashboard ==={NC}\n")
    print(f"{BOLD}Checklist Status:{NC}")
    for s, c in stats["checklist"].items():
        print(f"  {_st(s)}{s:<14}{NC} {c}")
    print(f"\n{BOLD}Open Defects by Severity:{NC}")
    for s, c in stats["open_defects_by_severity"].items():
        print(f"  {_sev(s)}{s:<14}{NC} {c}")
    total = sum(stats["open_defects_by_severity"].values())
    print(f"\n{BOLD}Total open defects: {RED}{total}{NC}\n")


def cmd_export(args, db):
    out = db.export_json()
    if args.output:
        Path(args.output).write_text(out); print(f"{GREEN}Exported to {args.output}{NC}")
    else:
        print(out)


def build_parser():
    p = argparse.ArgumentParser(prog="quality-control",
                                description="BlackRoad Quality Control - Checklist and Defect Tracker")
    sub = p.add_subparsers(dest="command", required=True)
    lp = sub.add_parser("list", help="List checklist items or defects")
    lp.add_argument("type", choices=["checklist", "defects"])
    lp.add_argument("--category"); lp.add_argument("--filter-status", dest="filter_status")
    ap = sub.add_parser("add", help="Add a checklist item or log a defect")
    ap.add_argument("type", choices=["checklist", "defect"])
    ap.add_argument("title")
    ap.add_argument("--category", default="general")
    ap.add_argument("--severity", choices=["low", "medium", "high", "critical"], default="medium")
    ap.add_argument("--description", default="")
    ap.add_argument("--component", default="general")
    ap.add_argument("--assignee", default="")
    sub.add_parser("status", help="Show dashboard")
    ep = sub.add_parser("export", help="Export data as JSON")
    ep.add_argument("--output", "-o")
    return p


def main():
    args = build_parser().parse_args()
    db = QualityControlDB()
    {"list": cmd_list, "add": cmd_add, "status": cmd_status, "export": cmd_export}[args.command](args, db)


if __name__ == "__main__":
    main()
