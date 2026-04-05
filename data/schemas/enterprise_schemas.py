"""
Pydantic + PySpark schemas cho dữ liệu mạng lưới doanh nghiệp
"""
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    DateType, BooleanType,
)


class CompanyStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISSOLVED = "dissolved"
    SUSPENDED = "suspended"


class CompanyType(str, Enum):
    LLC = "llc"
    JSC = "jsc"
    SOE = "soe"
    FDI = "fdi"
    PARTNERSHIP = "partnership"
    SOLE_PROPRIETOR = "sole_proprietor"


class RelationshipType(str, Enum):
    SHAREHOLDER = "SHAREHOLDER"
    LEGAL_REPRESENTATIVE = "LEGAL_REPRESENTATIVE"
    BOARD_MEMBER = "BOARD_MEMBER"
    SUBSIDIARY = "SUBSIDIARY"
    ASSOCIATED = "ASSOCIATED"
    SUPPLIER = "SUPPLIER"
    CUSTOMER = "CUSTOMER"
    PARTNER = "PARTNER"


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class CompanyModel(BaseModel):
    company_id: str
    name: str
    tax_code: str
    company_type: CompanyType
    status: CompanyStatus
    industry_code: str | None = None
    industry_name: str | None = None
    founded_date: date | None = None
    charter_capital: float | None = None
    address: str | None = None
    province: str | None = None
    country: str = "VN"
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_listed: bool = False
    stock_code: str | None = None


class PersonModel(BaseModel):
    person_id: str
    full_name: str
    national_id: str | None = None
    date_of_birth: date | None = None
    nationality: str = "VN"
    is_pep: bool = False
    is_sanctioned: bool = False


class RelationshipModel(BaseModel):
    source_id: str
    target_id: str
    source_type: str
    target_type: str
    rel_type: RelationshipType
    ownership_percent: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True


class TransactionModel(BaseModel):
    transaction_id: str
    from_company_id: str
    to_company_id: str
    amount: float
    currency: str = "VND"
    transaction_date: date
    transaction_type: str
    description: str | None = None
    is_flagged: bool = False


# ─── PySpark Schemas ──────────────────────────────────────────────────────────

COMPANY_SPARK_SCHEMA = StructType([
    StructField("company_id", StringType(), False),
    StructField("name", StringType(), False),
    StructField("tax_code", StringType(), True),
    StructField("company_type", StringType(), True),
    StructField("status", StringType(), True),
    StructField("industry_code", StringType(), True),
    StructField("industry_name", StringType(), True),
    StructField("founded_date", DateType(), True),
    StructField("charter_capital", DoubleType(), True),
    StructField("address", StringType(), True),
    StructField("province", StringType(), True),
    StructField("country", StringType(), True),
    StructField("risk_score", DoubleType(), True),
    StructField("is_listed", BooleanType(), True),
    StructField("stock_code", StringType(), True),
])

RELATIONSHIP_SPARK_SCHEMA = StructType([
    StructField("source_id", StringType(), False),
    StructField("target_id", StringType(), False),
    StructField("source_type", StringType(), True),
    StructField("target_type", StringType(), True),
    StructField("rel_type", StringType(), False),
    StructField("ownership_percent", DoubleType(), True),
    StructField("start_date", DateType(), True),
    StructField("end_date", DateType(), True),
    StructField("is_active", BooleanType(), True),
])

PERSON_SPARK_SCHEMA = StructType([
    StructField("person_id", StringType(), False),
    StructField("full_name", StringType(), True),
    StructField("nationality", StringType(), True),
    StructField("is_pep", BooleanType(), True),
    StructField("is_sanctioned", BooleanType(), True),
])

ADDRESS_SPARK_SCHEMA = StructType([
    StructField("address_id", StringType(), False),
    StructField("address", StringType(), True),
    StructField("name", StringType(), True),
    StructField("country", StringType(), True),
])

TRANSACTION_SPARK_SCHEMA = StructType([
    StructField("transaction_id", StringType(), False),
    StructField("from_company_id", StringType(), False),
    StructField("to_company_id", StringType(), False),
    StructField("amount", DoubleType(), False),
    StructField("currency", StringType(), True),
    StructField("transaction_date", DateType(), False),
    StructField("transaction_type", StringType(), True),
    StructField("description", StringType(), True),
    StructField("is_flagged", BooleanType(), True),
])

# ─── Panama/Bahamas/Paradise Papers raw schemas ─────────────────────────────

PANAMA_ENTITIES_SPARK_SCHEMA = StructType([
    StructField("node_id", StringType(), False),
    StructField("name", StringType(), True),
    StructField("original_name", StringType(), True),
    StructField("former_name", StringType(), True),
    StructField("jurisdiction", StringType(), True),
    StructField("jurisdiction_description", StringType(), True),
    StructField("company_type", StringType(), True),
    StructField("address", StringType(), True),
    StructField("internal_id", StringType(), True),
    StructField("incorporation_date", StringType(), True),
    StructField("inactivation_date", StringType(), True),
    StructField("struck_off_date", StringType(), True),
    StructField("dorm_date", StringType(), True),
    StructField("status", StringType(), True),
    StructField("service_provider", StringType(), True),
    StructField("ibcRUC", StringType(), True),
    StructField("country_codes", StringType(), True),
    StructField("countries", StringType(), True),
    StructField("sourceID", StringType(), True),
    StructField("valid_until", StringType(), True),
    StructField("note", StringType(), True),
])

PANAMA_OFFICERS_SPARK_SCHEMA = StructType([
    StructField("node_id", StringType(), False),
    StructField("name", StringType(), True),
    StructField("countries", StringType(), True),
    StructField("country_codes", StringType(), True),
    StructField("sourceID", StringType(), True),
    StructField("valid_until", StringType(), True),
    StructField("note", StringType(), True),
])

PANAMA_INTERMEDIARIES_SPARK_SCHEMA = StructType([
    StructField("node_id", StringType(), False),
    StructField("name", StringType(), True),
    StructField("status", StringType(), True),
    StructField("internal_id", StringType(), True),
    StructField("address", StringType(), True),
    StructField("countries", StringType(), True),
    StructField("country_codes", StringType(), True),
    StructField("sourceID", StringType(), True),
    StructField("valid_until", StringType(), True),
    StructField("note", StringType(), True),
])

PANAMA_OTHERS_SPARK_SCHEMA = StructType([
    StructField("node_id", StringType(), False),
    StructField("name", StringType(), True),
    StructField("type", StringType(), True),
    StructField("incorporation_date", StringType(), True),
    StructField("struck_off_date", StringType(), True),
    StructField("closed_date", StringType(), True),
    StructField("jurisdiction", StringType(), True),
    StructField("jurisdiction_description", StringType(), True),
    StructField("countries", StringType(), True),
    StructField("country_codes", StringType(), True),
    StructField("sourceID", StringType(), True),
    StructField("valid_until", StringType(), True),
    StructField("note", StringType(), True),
])

PANAMA_ADDRESSES_SPARK_SCHEMA = StructType([
    StructField("node_id", StringType(), False),
    StructField("address", StringType(), True),
    StructField("name", StringType(), True),
    StructField("countries", StringType(), True),
    StructField("country_codes", StringType(), True),
    StructField("sourceID", StringType(), True),
    StructField("valid_until", StringType(), True),
    StructField("note", StringType(), True),
])

PANAMA_RELATIONSHIPS_SPARK_SCHEMA = StructType([
    StructField("node_id_start", StringType(), False),
    StructField("node_id_end", StringType(), False),
    StructField("rel_type", StringType(), True),
    StructField("link", StringType(), True),
    StructField("status", StringType(), True),
    StructField("start_date", StringType(), True),
    StructField("end_date", StringType(), True),
    StructField("sourceID", StringType(), True),
])
