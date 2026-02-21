"""Automated Analytics Engine powered by LangGraph.

Uses an agentic workflow to:
1. Load tables and data from ingested PDFs stored in MongoDB / ChromaDB.
2. Build pandas DataFrames from extracted HTML tables.
3. Answer user questions by selecting the right tool (pandas query,
   metric extraction, trend analysis, chart generation) via an LLM
   tool-calling agent orchestrated through LangGraph.

Architecture
------------
The LangGraph state-graph has three nodes:

    [planner]  →  [tool_executor]  →  [synthesiser]
       ↑               │
       └───────────────┘  (loop if more tools needed)

Tools available to the agent:
- ``query_dataframe`` — run pandas expressions on loaded tables.
- ``extract_metrics`` — pull standard financial ratios / KPIs.
- ``compare_documents`` — cross-document comparison.
- ``generate_chart`` — create a Matplotlib chart, return base-64 PNG.
- ``search_vectors`` — semantic search over ChromaDB collections.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Sequence

import pandas as pd
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Pydantic schemas for tool arguments ────────────────────────────
class QueryDataFrameArgs(BaseModel):
    """Arguments for the query_dataframe tool."""
    expression: str = Field(description="A pandas expression to evaluate on the loaded DataFrame, e.g. 'df[df[\"Revenue\"] > 1000]' or 'df.describe()'")
    table_index: int = Field(default=0, description="Index of the loaded table to query (0-based)")


class ExtractMetricsArgs(BaseModel):
    """Arguments for the extract_metrics tool."""
    metric_names: list[str] = Field(description="List of metric names to extract, e.g. ['Revenue', 'Net Profit', 'EPS', 'ROE']")
    document_id: str | None = Field(default=None, description="Specific document to extract from. None = all loaded.")


class CompareDocsArgs(BaseModel):
    """Arguments for the compare_documents tool."""
    metric: str = Field(description="The metric to compare across documents, e.g. 'Revenue'")
    document_ids: list[str] = Field(default_factory=list, description="Document IDs to compare. Empty = all loaded.")


class GenerateChartArgs(BaseModel):
    """Arguments for the generate_chart tool."""
    chart_type: Literal["bar", "line", "pie", "radar", "heatmap"] = Field(description="Type of chart to generate")
    title: str = Field(default="", description="Chart title")
    data_expression: str = Field(description="Pandas expression that produces the data to plot, e.g. 'df[[\"Company\",\"Revenue\"]]'")
    x_label: str = Field(default="", description="X-axis label")
    y_label: str = Field(default="", description="Y-axis label")
    table_index: int = Field(default=0, description="Index of the loaded table to use (0-based)")


class SearchVectorsArgs(BaseModel):
    """Arguments for the search_vectors tool."""
    query: str = Field(description="Natural-language search query")
    collection: str = Field(default="financial_documents", description="ChromaDB collection to search")
    top_k: int = Field(default=5, description="Number of results to return")


class ListTablesArgs(BaseModel):
    """Arguments for the list_all_tables tool."""
    document_id: str | None = Field(default=None, description="Filter by document ID. None = show all loaded.")


class InspectTableArgs(BaseModel):
    """Arguments for the inspect_table tool."""
    table_index: int = Field(description="Index of the table to inspect (0-based)")
    num_rows: int = Field(default=5, description="Number of rows to preview")


class RunPandasCodeArgs(BaseModel):
    """Arguments for the run_pandas_code tool."""
    code: str = Field(description="Multi-line Python/pandas code to execute. All loaded tables are available as tables[0], tables[1], etc. Each is a dict with a 'dataframe' key.")
    table_index: int = Field(default=0, description="Primary table index; available as 'df' in the code")


# ── Tool descriptors (for LLM function-calling) ───────────────────
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_all_tables",
            "description": "List all available tables with their metadata (source file, page, type, columns, row count). Use this FIRST to understand what data is available before running queries.",
            "parameters": ListTablesArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_table",
            "description": "Preview the structure and first N rows of a specific table. Use this to understand column types and content before writing complex queries.",
            "parameters": InspectTableArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_dataframe",
            "description": "Execute a single pandas expression on a loaded financial table. The table is available as 'df'. E.g. 'df.describe()', 'df[df[\"Revenue\"] > 1000]'.",
            "parameters": QueryDataFrameArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_pandas_code",
            "description": "Execute multi-line Python/pandas code for complex analysis (aggregations, pivots, joins, computations). The primary table is 'df'; all tables are in 'tables' list. Use 'result' variable to return output.",
            "parameters": RunPandasCodeArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_metrics",
            "description": "Extract standard financial metrics (Revenue, Net Profit, EBITDA, EPS, ROE, Debt/Equity, Current Ratio, etc.) from loaded tables.",
            "parameters": ExtractMetricsArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_documents",
            "description": "Compare a specific financial metric across multiple documents / companies / fiscal years.",
            "parameters": CompareDocsArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": "Generate a chart (bar, line, pie, radar, heatmap) from table data and return it as a base-64 encoded PNG image.",
            "parameters": GenerateChartArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_vectors",
            "description": "Perform a semantic search over ChromaDB to find relevant regulatory rules, financial document sections, or disclosure requirements.",
            "parameters": SearchVectorsArgs.model_json_schema(),
        },
    },
]


# ── Agent state ────────────────────────────────────────────────────
class AnalyticsState(BaseModel):
    """Mutable state flowing through the LangGraph."""
    messages: list[dict[str, Any]] = Field(default_factory=list)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    iterations: int = 0
    max_iterations: int = 8
    finished: bool = False


# ── Helpers ────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a Senior Financial Analyst AI Agent for the NFRA Compliance Engine.
You have access to financial tables extracted from PDF documents (annual reports,
balance sheets, P&L statements, audit reports) that can be loaded as pandas DataFrames.

Your workflow (follow this order):
1. **list_all_tables** – ALWAYS call this first to see what tables are available.
2. **inspect_table** – Preview promising tables to understand their structure.
3. **query_dataframe** or **run_pandas_code** – Analyse the data.
4. **generate_chart** – Visualise results when helpful.
5. **extract_metrics** / **compare_documents** – For standard KPIs and comparisons.
6. **search_vectors** – Search the regulatory knowledge base for context.

Guidelines:
- ALWAYS start by listing and then inspecting relevant tables before running queries.
- Use `run_pandas_code` for multi-step analysis (aggregations, pivots, joins).
  Put your final answer in a variable called `result`.
- When generating charts, produce clear, publication-quality visuals.
- Cite specific numbers from the data to support your answers.
- If a question cannot be answered from the loaded data, say so clearly.
- Think step-by-step. When you have enough information, respond directly
  WITHOUT calling another tool.
"""

_MAX_TOOL_ITERATIONS = 8


def _html_table_to_dataframe(html: str) -> pd.DataFrame:
    """Convert an HTML table string to a pandas DataFrame."""
    try:
        dfs = pd.read_html(io.StringIO(html))
        if dfs:
            return dfs[0]
    except Exception:
        pass
    return pd.DataFrame()


def _plain_text_table_to_dataframe(text: str) -> pd.DataFrame:
    """Best-effort parse of a plain-text table into a DataFrame."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        return pd.DataFrame()

    rows: list[list[str]] = []
    for line in lines:
        cells = re.split(r"\s{2,}|\t|\|", line)
        cells = [c.strip() for c in cells if c.strip()]
        if cells:
            rows.append(cells)

    if not rows:
        return pd.DataFrame()

    max_cols = max(len(r) for r in rows)
    normalised = [r + [""] * (max_cols - len(r)) for r in rows]

    header = normalised[0]
    data = normalised[1:]
    return pd.DataFrame(data, columns=header)


class AnalyticsEngine:
    """LangGraph-powered agentic analytics engine.

    Parameters
    ----------
    vector_store:
        VectorStoreService instance for ChromaDB semantic search.
    embedding_service:
        EmbeddingService for generating query embeddings.
    mongo_service:
        MongoService for loading documents / tables from MongoDB.
    api_key:
        OpenAI API key.
    model:
        LLM model name.
    """

    _MAX_TABLES = 15
    _MAX_SUMMARY_CHARS = 6000
    _MAX_TABLE_PREVIEW_ROWS = 2
    _MAX_COLS_SHOWN = 8
    _RATE_LIMIT_RETRIES = 3
    _RATE_LIMIT_BACKOFF = 5  # seconds, doubles each retry

    def __init__(
        self,
        vector_store: Any,
        embedding_service: Any,
        mongo_service: Any,
        api_key: str = "",
        model: str = "gpt-4.1-mini",
    ) -> None:
        self._vs = vector_store
        self._emb = embedding_service
        self._mongo = mongo_service
        self._llm = ChatOpenAI(
            model=model,
            temperature=0.1,
            api_key=api_key,
            max_tokens=4096,
        )
        self._dataframes: dict[str, list[pd.DataFrame]] = {}

    # ── Public API ─────────────────────────────────────────────────

    async def analyse(
        self,
        question: str,
        document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the full agentic analysis loop.

        The agent first receives a lightweight table catalogue (no data),
        then uses tools to inspect and query only the tables it needs.

        Returns a dict with keys:
        - ``answer``: str -- the final natural-language answer
        - ``charts``: list[str] -- base-64 PNG images
        - ``metrics``: dict -- extracted metrics
        - ``tables_loaded``: int
        """
        all_tables = await self._load_tables(document_ids)

        relevant = self._rank_tables_by_relevance(all_tables, question)
        loaded_tables = relevant[: self._MAX_TABLES]

        catalogue = self._build_table_catalogue(loaded_tables)

        user_content = (
            f"{len(loaded_tables)} table(s) available from "
            f"{len(set(t['document_id'] for t in loaded_tables))} document(s).\n\n"
            f"Table catalogue:\n{catalogue}\n\n"
            f"User question: {question}\n\n"
            "Start by calling list_all_tables or inspect_table to understand the data, "
            "then use the appropriate tools to answer."
        )

        llm_with_tools = self._llm.bind(tools=TOOL_DEFINITIONS)

        messages: list[BaseMessage] = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        charts: list[str] = []
        metrics: dict[str, Any] = {}

        for iteration in range(_MAX_TOOL_ITERATIONS):
            response: AIMessage = await self._invoke_with_retry(
                llm_with_tools, messages
            )

            messages.append(response)

            if not response.tool_calls:
                return {
                    "answer": response.content or "",
                    "charts": charts,
                    "metrics": metrics,
                    "tables_loaded": len(loaded_tables),
                }

            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]

                try:
                    result = await self._execute_tool(
                        tool_name, tool_args, loaded_tables, charts, metrics
                    )
                except Exception as exc:
                    result = f"Tool error: {exc}"

                tool_content = str(result)
                if len(tool_content) > 4000:
                    tool_content = tool_content[:4000] + "\n... (truncated)"
                messages.append(
                    ToolMessage(content=tool_content, tool_call_id=tool_id)
                )

        final_response = await self._invoke_with_retry(self._llm, messages)
        return {
            "answer": final_response.content or "",
            "charts": charts,
            "metrics": metrics,
            "tables_loaded": len(loaded_tables),
        }

    async def _invoke_with_retry(
        self, llm: Any, messages: list[BaseMessage]
    ) -> AIMessage:
        """Invoke the LLM with exponential-backoff retry on rate-limit errors."""
        import openai as _openai

        backoff = self._RATE_LIMIT_BACKOFF
        for attempt in range(self._RATE_LIMIT_RETRIES):
            try:
                return await llm.ainvoke(messages)
            except _openai.RateLimitError:
                if attempt == self._RATE_LIMIT_RETRIES - 1:
                    raise
                logger.warning(
                    "Rate limit hit (attempt %d/%d), backing off %ds",
                    attempt + 1, self._RATE_LIMIT_RETRIES, backoff,
                )
                await asyncio.sleep(backoff)
                backoff *= 2
        raise RuntimeError("Unreachable")

    async def get_document_tables(
        self, document_id: str
    ) -> list[dict[str, Any]]:
        """Return table metadata for a single document."""
        doc = await self._mongo.find_by_id("documents", document_id)
        if not doc:
            return []
        tables = doc.get("tables", [])
        return [
            {
                "table_id": t.get("table_id", f"table_{i}"),
                "page_number": t.get("page_number", 0),
                "financial_statement_type": t.get("financial_statement_type"),
                "columns": t.get("column_headers", []),
                "rows": len(t.get("row_labels", [])),
                "has_html": bool(t.get("html")),
            }
            for i, t in enumerate(tables)
        ]

    async def get_financial_metrics(
        self,
        document_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Extract standard financial metrics from loaded tables."""
        loaded = await self._load_tables(document_ids)
        return self._extract_all_metrics(loaded)

    async def get_risk_indicators(
        self,
        document_id: str,
    ) -> list[dict[str, Any]]:
        """Scan a document for risk indicators using the LLM."""
        doc = await self._mongo.find_by_id("documents", document_id)
        if not doc:
            return []

        sections_text = ""
        for s in doc.get("sections", []):
            title = s.get("title", "Unknown Section")
            elements = s.get("elements", [])
            section_text = "\n".join(e.get("text", "") for e in elements[:5])
            sections_text += f"\n## {title}\n{section_text[:1000]}\n"

        prompt = (
            "You are a financial risk analyst. Analyse the following document sections "
            "and identify risk indicators. Look for:\n"
            "- Going concern qualifications\n"
            "- Material weaknesses\n"
            "- Unusual related-party transactions\n"
            "- Significant changes in accounting policies\n"
            "- Qualified audit opinions\n"
            "- Contingent liabilities\n"
            "- Regulatory non-compliance mentions\n\n"
            f"Document: {doc.get('filename', 'Unknown')}\n\n"
            f"Sections:\n{sections_text[:6000]}\n\n"
            "Respond in JSON array format:\n"
            '[{"indicator": "...", "severity": "high|medium|low", '
            '"description": "...", "evidence": "...", "section": "..."}]'
        )

        messages = [
            SystemMessage(content="You are a financial risk analysis expert. Always respond with valid JSON only."),
            HumanMessage(content=prompt),
        ]
        try:
            response = await self._llm.ainvoke(messages)
            text = response.content.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*", "", text)
                text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
        except Exception:
            logger.exception("Risk indicator extraction failed")
            return []

    async def get_trend_data(
        self,
        document_ids: list[str],
        metric: str,
    ) -> list[dict[str, Any]]:
        """Extract a metric across multiple documents for trend analysis."""
        results: list[dict[str, Any]] = []
        for doc_id in document_ids:
            doc = await self._mongo.find_by_id("documents", doc_id)
            if not doc:
                continue
            tables = await self._load_tables([doc_id])
            value = self._find_metric_in_tables(tables, metric)
            results.append({
                "document_id": doc_id,
                "filename": doc.get("filename", "Unknown"),
                "fiscal_year": doc.get("metadata", {}).get("fiscal_year", "N/A"),
                "metric": metric,
                "value": value,
            })
        return results

    # ── Tool execution ─────────────────────────────────────────────

    async def _execute_tool(
        self,
        name: str,
        args: dict[str, Any],
        tables: list[dict[str, Any]],
        charts: list[str],
        metrics: dict[str, Any],
    ) -> str:
        """Dispatch to the correct tool handler."""
        if name == "list_all_tables":
            return self._tool_list_all_tables(args, tables)
        elif name == "inspect_table":
            return self._tool_inspect_table(args, tables)
        elif name == "query_dataframe":
            return self._tool_query_dataframe(args, tables)
        elif name == "run_pandas_code":
            return self._tool_run_pandas_code(args, tables)
        elif name == "extract_metrics":
            return self._tool_extract_metrics(args, tables, metrics)
        elif name == "compare_documents":
            return self._tool_compare_documents(args, tables)
        elif name == "generate_chart":
            return await self._tool_generate_chart(args, tables, charts)
        elif name == "search_vectors":
            return await self._tool_search_vectors(args)
        else:
            return f"Unknown tool: {name}"

    def _tool_list_all_tables(
        self, args: dict[str, Any], tables: list[dict[str, Any]]
    ) -> str:
        """Return lightweight metadata for all loaded tables."""
        doc_filter = args.get("document_id")
        lines: list[str] = []
        for i, t in enumerate(tables):
            if doc_filter and t.get("document_id") != doc_filter:
                continue
            df: pd.DataFrame = t.get("dataframe", pd.DataFrame())
            cols = list(df.columns) if not df.empty else t.get("column_headers", [])
            lines.append(
                f"[{i}] source={t['source_file']}, "
                f"doc_id={t.get('document_id','?')}, "
                f"type={t.get('financial_statement_type', 'unknown')}, "
                f"page={t.get('page_number', '?')}, "
                f"rows={t.get('row_count', 0)}, cols={len(cols)}, "
                f"columns={cols[:12]}"
            )
        return "\n".join(lines) if lines else "No tables match the filter."

    def _tool_inspect_table(
        self, args: dict[str, Any], tables: list[dict[str, Any]]
    ) -> str:
        """Preview a specific table's structure and first N rows."""
        idx = args.get("table_index", 0)
        num_rows = min(args.get("num_rows", 5), 20)

        if idx >= len(tables):
            return f"Table index {idx} out of range ({len(tables)} available)."

        t = tables[idx]
        df: pd.DataFrame = t.get("dataframe", pd.DataFrame())
        if df.empty:
            return f"Table {idx} is empty."

        info_lines = [
            f"Table {idx}: {t['source_file']} (page {t.get('page_number','?')})",
            f"Type: {t.get('financial_statement_type', 'unknown')}",
            f"Shape: {df.shape[0]} rows x {df.shape[1]} columns",
            f"Columns: {list(df.columns)}",
            f"Dtypes:\n{df.dtypes.to_string()}",
            f"\nFirst {num_rows} rows:\n{df.head(num_rows).to_string()}",
        ]
        return "\n".join(info_lines)

    def _tool_run_pandas_code(
        self, args: dict[str, Any], tables: list[dict[str, Any]]
    ) -> str:
        """Execute multi-line Python/pandas code with access to all tables."""
        code = args.get("code", "")
        idx = args.get("table_index", 0)

        if not tables:
            return "No tables loaded."
        if idx >= len(tables):
            idx = 0

        import numpy as np

        df = tables[idx].get("dataframe", pd.DataFrame())
        all_dfs = [t.get("dataframe", pd.DataFrame()) for t in tables]

        local_ns: dict[str, Any] = {
            "df": df,
            "tables": tables,
            "all_dfs": all_dfs,
            "pd": pd,
            "np": np,
            "result": None,
        }

        try:
            exec(code, {"__builtins__": {}}, local_ns)
        except Exception as e:
            return f"Code execution error: {e}"

        result = local_ns.get("result")
        if result is None:
            return "Code executed but no `result` variable was set. Assign your output to `result`."
        if isinstance(result, pd.DataFrame):
            return result.to_string(max_rows=50, max_cols=20)
        if isinstance(result, pd.Series):
            return result.to_string(max_rows=50)
        return str(result)

    def _tool_query_dataframe(
        self, args: dict[str, Any], tables: list[dict[str, Any]]
    ) -> str:
        """Execute a pandas expression on a loaded table."""
        idx = args.get("table_index", 0)
        expression = args.get("expression", "")

        if not tables:
            return "No tables are loaded. Cannot execute query."

        if idx >= len(tables):
            return f"Table index {idx} out of range. {len(tables)} tables available (0-{len(tables)-1})."

        df = tables[idx].get("dataframe")
        if df is None or df.empty:
            return f"Table {idx} is empty or could not be parsed."

        safe_globals = {"__builtins__": {}}
        safe_locals = {"df": df, "pd": pd}

        try:
            result = eval(expression, safe_globals, safe_locals)
            if isinstance(result, pd.DataFrame):
                return result.to_string(max_rows=50, max_cols=20)
            elif isinstance(result, pd.Series):
                return result.to_string(max_rows=50)
            else:
                return str(result)
        except Exception as e:
            return f"Expression error: {e}"

    def _tool_extract_metrics(
        self,
        args: dict[str, Any],
        tables: list[dict[str, Any]],
        metrics_store: dict[str, Any],
    ) -> str:
        """Extract named metrics from tables."""
        metric_names = args.get("metric_names", [])
        results: dict[str, Any] = {}

        for metric_name in metric_names:
            value = self._find_metric_in_tables(tables, metric_name)
            results[metric_name] = value

        metrics_store.update(results)
        return json.dumps(results, indent=2, default=str)

    def _tool_compare_documents(
        self, args: dict[str, Any], tables: list[dict[str, Any]]
    ) -> str:
        """Compare a metric across loaded tables."""
        metric = args.get("metric", "")
        comparison: list[dict[str, Any]] = []

        for i, t in enumerate(tables):
            value = self._find_metric_in_tables([t], metric)
            comparison.append({
                "table_index": i,
                "source": t.get("source_file", f"Table {i}"),
                "document_id": t.get("document_id", ""),
                "metric": metric,
                "value": value,
            })

        return json.dumps(comparison, indent=2, default=str)

    async def _tool_generate_chart(
        self,
        args: dict[str, Any],
        tables: list[dict[str, Any]],
        charts: list[str],
    ) -> str:
        """Generate a chart and return base-64 PNG."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        chart_type = args.get("chart_type", "bar")
        title = args.get("title", "Chart")
        data_expr = args.get("data_expression", "df")
        x_label = args.get("x_label", "")
        y_label = args.get("y_label", "")
        idx = args.get("table_index", 0)

        if not tables:
            return "No tables loaded for chart generation."
        if idx >= len(tables):
            return f"Table index {idx} out of range."

        df = tables[idx].get("dataframe")
        if df is None or df.empty:
            return "Table is empty."

        safe_globals = {"__builtins__": {}}
        safe_locals = {"df": df, "pd": pd}

        try:
            plot_data = eval(data_expr, safe_globals, safe_locals)
        except Exception as e:
            return f"Data expression error: {e}"

        if not isinstance(plot_data, (pd.DataFrame, pd.Series)):
            return "Data expression must return a DataFrame or Series."

        loop = asyncio.get_running_loop()

        def _render() -> str:
            fig, ax = plt.subplots(figsize=(10, 6))
            fig.patch.set_facecolor("#fafafa")
            ax.set_facecolor("#fafafa")

            if chart_type == "bar":
                if isinstance(plot_data, pd.Series):
                    plot_data.plot.bar(ax=ax, color="#0071e3", edgecolor="white")
                else:
                    plot_data.plot.bar(ax=ax, edgecolor="white")
            elif chart_type == "line":
                if isinstance(plot_data, pd.Series):
                    plot_data.plot.line(ax=ax, color="#0071e3", linewidth=2, marker="o")
                else:
                    plot_data.plot.line(ax=ax, linewidth=2, marker="o")
            elif chart_type == "pie":
                if isinstance(plot_data, pd.Series):
                    plot_data.plot.pie(ax=ax, autopct="%1.1f%%")
                else:
                    plot_data.iloc[:, 0].plot.pie(ax=ax, autopct="%1.1f%%")
            elif chart_type == "heatmap":
                try:
                    numeric = plot_data.select_dtypes(include="number")
                    im = ax.imshow(numeric.values, aspect="auto", cmap="Blues")
                    ax.set_xticks(range(len(numeric.columns)))
                    ax.set_xticklabels(numeric.columns, rotation=45, ha="right")
                    fig.colorbar(im, ax=ax)
                except Exception:
                    plot_data.plot.bar(ax=ax)
            else:
                if isinstance(plot_data, pd.Series):
                    plot_data.plot.bar(ax=ax, color="#0071e3")
                else:
                    plot_data.plot.bar(ax=ax)

            ax.set_title(title, fontsize=14, fontweight="bold", pad=12)
            if x_label:
                ax.set_xlabel(x_label)
            if y_label:
                ax.set_ylabel(y_label)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            plt.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode()

        b64 = await loop.run_in_executor(None, _render)
        charts.append(b64)
        return f"Chart generated successfully (chart index {len(charts) - 1}). The image has been saved."

    async def _tool_search_vectors(self, args: dict[str, Any]) -> str:
        """Perform a semantic search over ChromaDB."""
        query = args.get("query", "")
        collection = args.get("collection", "financial_documents")
        top_k = args.get("top_k", 5)

        try:
            embedding = await self._emb.embed_single(query)
            if not embedding:
                return "Could not generate embedding for the query."

            results = await self._vs.query(
                collection_name=collection,
                query_embedding=embedding,
                n_results=top_k,
            )

            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]

            formatted: list[str] = []
            for doc, meta, dist in zip(docs, metas, dists):
                source = meta.get("source_file", "Unknown")
                section = meta.get("section_path", "")
                score = round(max(0.0, 1.0 - dist), 4)
                formatted.append(
                    f"[Score: {score}] {source} | {section}\n{(doc or '')[:300]}"
                )

            return "\n\n---\n\n".join(formatted) if formatted else "No results found."
        except Exception as e:
            return f"Vector search error: {e}"

    # ── Internal helpers ───────────────────────────────────────────

    def _rank_tables_by_relevance(
        self, tables: list[dict[str, Any]], question: str
    ) -> list[dict[str, Any]]:
        """Score and sort tables by relevance to the user's question.

        Uses keyword overlap between the question and table metadata
        (column headers, financial_statement_type, source_file).
        Tables with higher relevance scores come first.
        """
        if not question or not tables:
            return tables

        q_tokens = set(re.findall(r"\w+", question.lower()))
        financial_keywords = {
            "revenue", "profit", "loss", "income", "expense", "asset",
            "liability", "equity", "cash", "flow", "balance", "sheet",
            "ebitda", "eps", "roe", "ratio", "debt", "dividend",
            "operating", "net", "gross", "total", "current",
        }
        q_finance = q_tokens & financial_keywords

        scored: list[tuple[float, int, dict[str, Any]]] = []
        for idx, t in enumerate(tables):
            score = 0.0
            df: pd.DataFrame = t.get("dataframe", pd.DataFrame())
            cols = [str(c).lower() for c in df.columns] if not df.empty else []
            col_tokens = set()
            for c in cols:
                col_tokens.update(re.findall(r"\w+", c))

            overlap = len(q_tokens & col_tokens)
            score += overlap * 2.0

            finance_col_overlap = len(q_finance & col_tokens)
            score += finance_col_overlap * 3.0

            fst = (t.get("financial_statement_type") or "").lower()
            if fst:
                fst_tokens = set(re.findall(r"\w+", fst))
                score += len(q_tokens & fst_tokens) * 4.0

            src = (t.get("source_file") or "").lower()
            src_tokens = set(re.findall(r"\w+", src))
            score += len(q_tokens & src_tokens) * 1.5

            if t.get("row_count", 0) > 2:
                score += 0.5

            scored.append((score, idx, t))

        scored.sort(key=lambda x: (-x[0], x[1]))
        return [item[2] for item in scored]

    def _build_table_catalogue(self, tables: list[dict[str, Any]]) -> str:
        """Build a compact catalogue string listing table metadata only (no data)."""
        if not tables:
            return "No tables available."

        lines: list[str] = []
        for i, t in enumerate(tables):
            df: pd.DataFrame = t.get("dataframe", pd.DataFrame())
            cols = list(df.columns) if not df.empty else t.get("column_headers", [])
            col_preview = cols[:8]
            if len(cols) > 8:
                col_preview.append(f"+{len(cols) - 8} more")
            lines.append(
                f"[{i}] {t['source_file']} | "
                f"type={t.get('financial_statement_type', 'unknown')} | "
                f"page={t.get('page_number', '?')} | "
                f"{t.get('row_count', 0)} rows | "
                f"cols={col_preview}"
            )
        return "\n".join(lines)

    async def _load_tables(
        self, document_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Load and parse tables from MongoDB documents into DataFrames."""
        query: dict[str, Any] = {}
        if document_ids:
            from bson import ObjectId
            oid_list = []
            for did in document_ids:
                try:
                    oid_list.append(ObjectId(did))
                except Exception:
                    pass
            if oid_list:
                query["_id"] = {"$in": oid_list}
        else:
            query["tables_count"] = {"$gt": 0}

        docs = await self._mongo.find_many("documents", query, limit=10)

        all_tables: list[dict[str, Any]] = []
        for doc in docs:
            doc_id = doc.get("_id", "")
            filename = doc.get("filename", "Unknown")
            tables = doc.get("tables", [])

            for i, t in enumerate(tables):
                html = t.get("html", "")
                plain = t.get("plain_text", "")

                df = pd.DataFrame()
                if html:
                    df = _html_table_to_dataframe(html)
                if df.empty and plain:
                    df = _plain_text_table_to_dataframe(plain)

                for col in df.columns:
                    try:
                        cleaned = df[col].astype(str).str.replace(",", "").str.replace("₹", "").str.replace("$", "").str.strip()
                        df[col] = pd.to_numeric(cleaned, errors="coerce").fillna(df[col])
                    except Exception:
                        pass

                all_tables.append({
                    "document_id": str(doc_id),
                    "source_file": filename,
                    "table_index": i,
                    "table_id": t.get("table_id", f"table_{i}"),
                    "page_number": t.get("page_number", 0),
                    "financial_statement_type": t.get("financial_statement_type"),
                    "column_headers": t.get("column_headers", []),
                    "dataframe": df,
                    "row_count": len(df),
                    "col_count": len(df.columns),
                })

            # Also parse inline tables from elements
            elements = doc.get("elements", [])
            for elem in elements:
                if elem.get("element_type") == "Table":
                    html = elem.get("html", "")
                    text = elem.get("text", "")
                    df = pd.DataFrame()
                    if html:
                        df = _html_table_to_dataframe(html)
                    if df.empty and text:
                        df = _plain_text_table_to_dataframe(text)
                    if not df.empty:
                        for col in df.columns:
                            try:
                                cleaned = df[col].astype(str).str.replace(",", "").str.replace("₹", "").str.replace("$", "").str.strip()
                                df[col] = pd.to_numeric(cleaned, errors="coerce").fillna(df[col])
                            except Exception:
                                pass

                        all_tables.append({
                            "document_id": str(doc_id),
                            "source_file": filename,
                            "table_index": len(all_tables),
                            "table_id": elem.get("element_id", f"elem_table_{len(all_tables)}"),
                            "page_number": elem.get("page_number", 0),
                            "financial_statement_type": None,
                            "column_headers": list(df.columns),
                            "dataframe": df,
                            "row_count": len(df),
                            "col_count": len(df.columns),
                        })

        return all_tables[: self._MAX_TABLES]

    def _find_metric_in_tables(
        self, tables: list[dict[str, Any]], metric: str
    ) -> Any:
        """Search for a metric name in table columns / rows and return value."""
        metric_lower = metric.lower().strip()

        for t in tables:
            df: pd.DataFrame = t.get("dataframe", pd.DataFrame())
            if df.empty:
                continue

            for col in df.columns:
                if metric_lower in str(col).lower():
                    numeric = pd.to_numeric(df[col], errors="coerce")
                    valid = numeric.dropna()
                    if not valid.empty:
                        return float(valid.iloc[-1])

            for _, row in df.iterrows():
                row_vals = row.values.tolist()
                for j, val in enumerate(row_vals):
                    if metric_lower in str(val).lower():
                        for k in range(j + 1, len(row_vals)):
                            try:
                                num = float(
                                    str(row_vals[k])
                                    .replace(",", "")
                                    .replace("₹", "")
                                    .replace("$", "")
                                    .strip()
                                )
                                return num
                            except (ValueError, TypeError):
                                continue

        return None

    def _extract_all_metrics(
        self, tables: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Extract a standard set of financial metrics."""
        standard_metrics = [
            "Revenue", "Net Profit", "EBITDA", "EPS",
            "ROE", "Debt/Equity", "Current Ratio",
            "Total Assets", "Total Liabilities",
            "Operating Profit", "Cash Flow from Operations",
        ]
        result: dict[str, Any] = {}
        for m in standard_metrics:
            val = self._find_metric_in_tables(tables, m)
            if val is not None:
                result[m] = val
        return result
