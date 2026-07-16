"""Self-contained mini corpus for OFFLINE conformance doubles.

Plugin authors seed their canned transports/doubles with these so the suite
runs credential-free. Deliberately independent of etki's own fake seed — the
conformance package must work without etki installed."""

from __future__ import annotations

from etki_api.models import CodeModule, Complexity, DocumentRef, WorkItem

SAMPLE_WORK_ITEMS = [
    WorkItem(
        id="CONF-1",
        title="Raporlama ekranına CSV dışa aktarım",
        description="mevcut rapor listesi csv olarak indirilebilsin",
        category="raporlama",
        status="closed",
        effort_seconds=14 * 3600,
    ),
    WorkItem(
        id="CONF-2",
        title="Ödeme sağlayıcı zaman aşımı düzeltmesi",
        description="ödeme çağrısı 30sn üstünde kopuyor",
        category="ödeme",
        status="closed",
        effort_seconds=6 * 3600,
    ),
]

SAMPLE_MODULES = [
    CodeModule(
        id="reporting",
        path="src/reporting.py",
        responsibilities=["rapor", "csv"],
        depends_on=["db"],
        complexity=Complexity(loc=420, cyclomatic=18, files=3),
    ),
    CodeModule(
        id="db",
        path="src/db.py",
        responsibilities=["veritabanı"],
        depended_by=["reporting"],
        complexity=Complexity(loc=210, cyclomatic=9, files=1),
    ),
]

SAMPLE_DOCUMENTS = [
    DocumentRef(id="doc-contract", name="sozlesme.md", path="/docs/sozlesme.md", source="conf"),
    DocumentRef(id="doc-scope", name="kapsam.md", path="/docs/kapsam.md", source="conf"),
]
