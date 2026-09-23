-- Schema-only fixture captured from the 2026-09-19 pre-feature-migration database.

-- Contains NO application rows or user data.

-- Represents Alembic revision 1d77e94a0fb5.

PRAGMA foreign_keys=OFF;

CREATE TABLE application_payments (
	id INTEGER NOT NULL, 
	application_id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	applicant_user_id INTEGER NOT NULL, 
	applicant_name VARCHAR(255) NOT NULL, 
	amount NUMERIC(10, 2) NOT NULL, 
	stripe_payment_intent_id VARCHAR(255), 
	status VARCHAR(20) NOT NULL, 
	paid_at DATETIME, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(application_id) REFERENCES lease_applications (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id), 
	FOREIGN KEY(applicant_user_id) REFERENCES users (id)
);

CREATE TABLE audit_log (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	organization_id INTEGER, 
	entity_type VARCHAR(50) NOT NULL, 
	entity_id INTEGER NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	field_name VARCHAR(100), 
	old_value TEXT, 
	new_value TEXT, 
	ip_address VARCHAR(45), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE lease_applications (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	unit_id INTEGER, 
	applicant_user_id INTEGER NOT NULL, 
	submitted_by_id INTEGER, 
	status VARCHAR(15) NOT NULL, 
	applicant_names TEXT, 
	occupant_names TEXT, 
	applicant_ssn VARCHAR(11), 
	applicant_phone VARCHAR(50), 
	applicant_email VARCHAR(255), 
	applicant_dob DATE, 
	move_in_date DATE, 
	lease_term_months INTEGER, 
	pet_details TEXT, 
	fee_amount NUMERIC(10, 2), 
	fee_waived BOOLEAN, 
	screening_provider VARCHAR(50), 
	screening_result TEXT, 
	screening_recommendation VARCHAR(50), 
	reviewed_by_id INTEGER, 
	reviewed_at DATETIME, 
	rejection_reason VARCHAR(500), 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id), 
	FOREIGN KEY(unit_id) REFERENCES units (id), 
	FOREIGN KEY(applicant_user_id) REFERENCES users (id), 
	FOREIGN KEY(submitted_by_id) REFERENCES users (id), 
	FOREIGN KEY(reviewed_by_id) REFERENCES users (id)
);

CREATE TABLE leases (
	id INTEGER NOT NULL, 
	unit_id INTEGER NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	start_date DATE NOT NULL, 
	end_date DATE NOT NULL, 
	monthly_rent NUMERIC(10, 2) NOT NULL, 
	security_deposit NUMERIC(10, 2) NOT NULL, 
	due_day INTEGER NOT NULL, 
	status VARCHAR(17) NOT NULL, 
	signed_at DATETIME, 
	signed_by_tenant BOOLEAN, 
	signed_by_manager BOOLEAN, 
	document_url VARCHAR(500), 
	notes TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unit_id) REFERENCES units (id), 
	FOREIGN KEY(tenant_id) REFERENCES users (id)
);

CREATE TABLE organization_email_settings (
	id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	from_email VARCHAR(255) NOT NULL, 
	from_name VARCHAR(255) NOT NULL, 
	reply_to_email VARCHAR(255), 
	smtp_host VARCHAR(255) NOT NULL, 
	smtp_port INTEGER NOT NULL, 
	smtp_user VARCHAR(255) NOT NULL, 
	smtp_password_encrypted VARCHAR(1024) NOT NULL, 
	smtp_use_tls BOOLEAN NOT NULL, 
	is_enabled BOOLEAN, 
	last_test_at DATETIME, 
	verified_at DATETIME, 
	last_error VARCHAR(500), 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE organization_screening_settings (
	id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	provider_slug VARCHAR(50), 
	is_enabled BOOLEAN, 
	api_key_encrypted TEXT, 
	api_secret_encrypted TEXT, 
	account_id VARCHAR(255), 
	application_fee NUMERIC(10, 2), 
	fee_waived_for_managers BOOLEAN, 
	auto_screen_on_apply BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE organizations (
	id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE password_reset_tokens (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	token VARCHAR(255) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	used BOOLEAN, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE payments (
	id INTEGER NOT NULL, 
	invoice_id INTEGER NOT NULL, 
	amount NUMERIC(10, 2) NOT NULL, 
	method VARCHAR(5) NOT NULL, 
	paid_at DATETIME NOT NULL, 
	external_id VARCHAR(255), 
	notes TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invoice_id) REFERENCES rent_invoices (id)
);

CREATE TABLE platform_settings (
	id INTEGER NOT NULL, 
	"key" VARCHAR(100) NOT NULL, 
	value TEXT, 
	description VARCHAR(500), 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE properties (
	id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	property_type VARCHAR(13) NOT NULL, 
	address_line1 VARCHAR(255) NOT NULL, 
	address_line2 VARCHAR(255), 
	city VARCHAR(100) NOT NULL, 
	state VARCHAR(50) NOT NULL, 
	zip_code VARCHAR(20) NOT NULL, 
	country VARCHAR(100) NOT NULL, 
	year_built INTEGER, 
	notes TEXT, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, description TEXT, square_feet INTEGER, year_renovated INTEGER, parking_spaces INTEGER, stories INTEGER, estimated_rent NUMERIC(10,2), security_deposit NUMERIC(10,2), ownership_status VARCHAR(50), deleted_at DATETIME, deleted_by_id INTEGER, delete_reason TEXT, parking_type VARCHAR(50), purchase_date DATE, purchase_price NUMERIC(12,2), current_market_value NUMERIC(12,2), mortgage_lender VARCHAR(255), mortgage_account_number VARCHAR(100), mortgage_original_amount NUMERIC(12,2), mortgage_current_balance NUMERIC(12,2), mortgage_interest_rate NUMERIC(5,2), mortgage_term_months INTEGER, mortgage_start_date DATE, mortgage_monthly_payment NUMERIC(10,2), mortgage_escrow_included BOOLEAN DEFAULT 0, payoff_date DATE, payoff_amount NUMERIC(12,2), pets_allowed BOOLEAN DEFAULT 0, pet_types_allowed VARCHAR(100), max_pets INTEGER, weight_limit_lbs INTEGER, breed_restrictions TEXT, pet_deposit NUMERIC(10,2), pet_rent NUMERIC(10,2), smoking_allowed BOOLEAN DEFAULT 0, lease_term_months INTEGER, available_from DATE, renters_insurance_required BOOLEAN DEFAULT 0, renters_insurance_min_coverage NUMERIC(12,2), renters_insurance_required_at_movein BOOLEAN DEFAULT 0, renters_insurance_notes TEXT, laundry_type VARCHAR(50), shared_laundry_location VARCHAR(255), shared_laundry_cost VARCHAR(100), shared_laundry_notes TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE property_assignments (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role VARCHAR(7) NOT NULL, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_property_user UNIQUE (property_id, user_id), 
	FOREIGN KEY(property_id) REFERENCES properties (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE property_expenses (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	category VARCHAR(11) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	expense_date DATE NOT NULL, 
	source VARCHAR(11) NOT NULL, 
	source_id INTEGER, 
	notes TEXT, 
	receipt_url VARCHAR(500), 
	created_by_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id), 
	FOREIGN KEY(created_by_id) REFERENCES users (id)
);

CREATE TABLE property_income (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	category VARCHAR(21) NOT NULL, 
	amount NUMERIC(12, 2) NOT NULL, 
	description VARCHAR(500) NOT NULL, 
	income_date DATE NOT NULL, 
	payer_name VARCHAR(255), 
	payer_user_id INTEGER, 
	source VARCHAR(12) NOT NULL, 
	source_id INTEGER, 
	notes TEXT, 
	created_by_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id), 
	FOREIGN KEY(payer_user_id) REFERENCES users (id), 
	FOREIGN KEY(created_by_id) REFERENCES users (id)
);

CREATE TABLE property_insurance (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	policy_type VARCHAR(10) NOT NULL, 
	provider VARCHAR(255) NOT NULL, 
	policy_number VARCHAR(100), 
	coverage_amount NUMERIC(12, 2), 
	deductible NUMERIC(12, 2), 
	premium_amount NUMERIC(10, 2), 
	premium_frequency VARCHAR(11) NOT NULL, 
	start_date DATE, 
	end_date DATE, 
	agent_name VARCHAR(255), 
	agent_phone VARCHAR(50), 
	agent_email VARCHAR(255), 
	document_url VARCHAR(500), 
	notes TEXT, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id)
);

CREATE TABLE property_tax_payments (
	id INTEGER NOT NULL, 
	tax_id INTEGER NOT NULL, 
	amount NUMERIC(10, 2) NOT NULL, 
	paid_at DATE NOT NULL, 
	period VARCHAR(50), 
