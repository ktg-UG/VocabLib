"""Supabase同期

ローカルSQLiteが正（source of truth）で、クラウドは同期先。
UIはこの層を一切待たない。失敗しても次回に持ち越すだけ。
"""
from .engine import SyncEngine, SyncResult
from .remote import SupabaseClient, is_configured

__all__ = ["SyncEngine", "SyncResult", "SupabaseClient", "is_configured"]
