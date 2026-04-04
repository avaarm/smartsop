"""Pydantic models for GMP document template schemas."""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    BATCH_RECORD = "batch_record"
    SOP = "sop"
    DEVIATION_REPORT = "deviation_report"
    CAPA = "capa"
    CHANGE_CONTROL = "change_control"


class Orientation(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"


class SectionType(str, Enum):
    APPROVAL_BLOCK = "approval_block"
    TABLE = "table"
    STEP_PROCEDURE = "step_procedure"
    REFERENCES = "references"
    ATTACHMENTS = "attachments"
    FLOWCHART = "flowchart"
    CHECKLIST = "checklist"
    FREE_TEXT = "free_text"
    EQUIPMENT_LIST = "equipment_list"
    MATERIALS_LIST = "materials_list"
    LABEL_ACCOUNTABILITY = "label_accountability"
    COMMENTS = "comments"
    REVIEW = "review"
    GENERAL_INSTRUCTIONS = "general_instructions"


class PageSize(BaseModel):
    width_dxa: int = 15840
    height_dxa: int = 12240


class Margins(BaseModel):
    top: int = 1080
    right: int = 720
    bottom: int = 720
    left: int = 720
    header: int = 1080
    footer: int = 1440
    gutter: int = 0


class FontConfig(BaseModel):
    name: str = "Calibri"
    size_half_pt: int = 22  # 11pt


class HeaderCell(BaseModel):
    type: str  # logo, title, page_number, doc_number, effective_date, revision
    text: Optional[str] = None
    bold: bool = False
    size_half_pt: Optional[int] = None
    alignment: str = "left"
    col_span: int = 1
    row_span: int = 1


class HeaderConfig(BaseModel):
    columns: int = 6
    column_widths: list[int] = Field(default_factory=lambda: [775, 1493, 5377, 2520, 1440, 2993])
    total_width: int = 14598
    row_height_dxa: int = 288
    rows: int = 3
    cells: list[list[HeaderCell]] = Field(default_factory=list)


class FooterConfig(BaseModel):
    text: str = "CONFIDENTIAL"
    organization: str = ""
    font_size_half_pt: int = 16  # 8pt
    bold: bool = True
    border_top: bool = True
    alignment: str = "center"


class ColumnDef(BaseModel):
    id: str
    title: str
    width_dxa: int
    fill_color: Optional[str] = None
    bold: bool = False
    alignment: str = "left"
    vertical_align: str = "center"


class TableConfig(BaseModel):
    total_width_dxa: int = 14580
    column_widths: list[int] = Field(default_factory=list)
    layout: str = "fixed"
    header_fill: str = "BFBFBF"
    label_fill: str = "F2F2F2"
    cell_vertical_align: str = "center"
    cell_spacing_before: int = 60
    cell_spacing_after: int = 60
    borders: bool = True


class StepColumn(BaseModel):
    id: str
    title: str
    width_dxa: int


class StepProcedureConfig(BaseModel):
    columns: list[StepColumn] = Field(default_factory=lambda: [
        StepColumn(id="instruction", title="Instruction", width_dxa=5400),
        StepColumn(id="variable", title="Variable", width_dxa=2160),
        StepColumn(id="result", title="Result / Actual", width_dxa=3240),
        StepColumn(id="performed_by", title="Performed By (Initials/Date)", width_dxa=1890),
        StepColumn(id="checked_by", title="Checked By (Initials/Date)", width_dxa=1890),
    ])
    header_fill: str = "BFBFBF"
    label_fill: str = "F2F2F2"


class SectionDefinition(BaseModel):
    id: str
    title: str
    type: SectionType
    required: bool = True
    table_config: Optional[TableConfig] = None
    columns: list[ColumnDef] = Field(default_factory=list)
    step_config: Optional[StepProcedureConfig] = None
    llm_prompt: Optional[str] = None
    conditional: Optional[dict] = None
    children: list[SectionDefinition] = Field(default_factory=list)
    default_data: Optional[dict] = None


class DocumentTemplate(BaseModel):
    id: str
    name: str
    doc_type: DocumentType
    orientation: Orientation = Orientation.LANDSCAPE
    page_size: PageSize = Field(default_factory=PageSize)
    margins: Margins = Field(default_factory=Margins)
    default_font: FontConfig = Field(default_factory=FontConfig)
    header_config: HeaderConfig = Field(default_factory=HeaderConfig)
    footer_config: FooterConfig = Field(default_factory=FooterConfig)
    sections: list[SectionDefinition] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
