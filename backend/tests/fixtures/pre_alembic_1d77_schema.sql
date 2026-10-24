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
	confirmation_number VARCHAR(100), 
	receipt_url VARCHAR(500), 
	is_paid_from_escrow BOOLEAN, 
	notes TEXT, 
	created_by_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tax_id) REFERENCES property_taxes (id), 
	FOREIGN KEY(created_by_id) REFERENCES users (id)
);

CREATE TABLE property_taxes (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	tax_authority VARCHAR(255) NOT NULL, 
	tax_type VARCHAR(16) NOT NULL, 
	parcel_number VARCHAR(100), 
	assessed_value NUMERIC(12, 2), 
	tax_rate_percent NUMERIC(6, 4), 
	annual_amount NUMERIC(12, 2), 
	payment_frequency VARCHAR(11) NOT NULL, 
	payment_amount NUMERIC(10, 2), 
	next_due_date DATE, 
	escrow_included BOOLEAN, 
	is_active BOOLEAN, 
	notes TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id)
);

CREATE TABLE property_utilities (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	utility_type VARCHAR(8) NOT NULL, 
	company_name VARCHAR(255) NOT NULL, 
	company_phone VARCHAR(50), 
	company_website VARCHAR(255), 
	paid_by VARCHAR(16) NOT NULL, 
	account_number VARCHAR(100), 
	account_holder_name VARCHAR(255), 
	setup_instructions TEXT, 
	internal_notes TEXT, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id)
);

CREATE TABLE rent_invoices (
	id INTEGER NOT NULL, 
	lease_id INTEGER NOT NULL, 
	period_start DATE NOT NULL, 
	period_end DATE NOT NULL, 
	due_date DATE NOT NULL, 
	amount_due NUMERIC(10, 2) NOT NULL, 
	amount_paid NUMERIC(10, 2) NOT NULL, 
	late_fee NUMERIC(10, 2) NOT NULL, 
	status VARCHAR(7) NOT NULL, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lease_id) REFERENCES leases (id)
);

CREATE TABLE screening_providers (
	id INTEGER NOT NULL, 
	slug VARCHAR(50) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	description TEXT, 
	pricing_info VARCHAR(255), 
	api_docs_url VARCHAR(500), 
	is_active BOOLEAN, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (slug)
);

CREATE TABLE sidebar_preferences (
	id INTEGER NOT NULL, 
	organization_id INTEGER NOT NULL, 
	"order" JSON NOT NULL, 
	hidden JSON NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP), 
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP), 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE CASCADE
);

CREATE TABLE tenant_insurance (
	id INTEGER NOT NULL, 
	lease_id INTEGER NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	provider VARCHAR(255), 
	policy_number VARCHAR(100), 
	coverage_amount NUMERIC(12, 2), 
	effective_date DATE, 
	expiration_date DATE, 
	document_url VARCHAR(500), 
	status VARCHAR(8) NOT NULL, 
	extraction_status VARCHAR(13) NOT NULL, 
	extracted_data TEXT, 
	verified_by_id INTEGER, 
	verified_at DATETIME, 
	rejection_reason VARCHAR(500), 
	notes TEXT, 
	uploaded_by_id INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lease_id) REFERENCES leases (id), 
	FOREIGN KEY(tenant_id) REFERENCES users (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id), 
	FOREIGN KEY(verified_by_id) REFERENCES users (id), 
	FOREIGN KEY(uploaded_by_id) REFERENCES users (id)
);

CREATE TABLE trash_pickup_schedule (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	pickup_type VARCHAR(10) NOT NULL, 
	day_of_week VARCHAR(20) NOT NULL, 
	frequency VARCHAR(20) NOT NULL, 
	time_window VARCHAR(100), 
	notes TEXT, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id)
);

CREATE TABLE units (
	id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	unit_number VARCHAR(50) NOT NULL, 
	bedrooms INTEGER NOT NULL, 
	bathrooms NUMERIC(3, 1) NOT NULL, 
	square_feet INTEGER, 
	monthly_rent NUMERIC(10, 2) NOT NULL, 
	security_deposit NUMERIC(10, 2), 
	is_available BOOLEAN, 
	is_active BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, pet_deposit NUMERIC(10,2), pet_rent NUMERIC(10,2), application_fee NUMERIC(10,2), admin_fee NUMERIC(10,2), available_from DATE, lease_term_months INTEGER, is_listed BOOLEAN DEFAULT 0, deleted_at DATETIME, deleted_by_id INTEGER, delete_reason TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_property_unit_number UNIQUE (property_id, unit_number), 
	FOREIGN KEY(property_id) REFERENCES properties (id)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	hashed_password VARCHAR(255) NOT NULL, 
	first_name VARCHAR(100) NOT NULL, 
	last_name VARCHAR(100) NOT NULL, 
	phone VARCHAR(50), 
	role VARCHAR(7) NOT NULL, 
	organization_id INTEGER, 
	is_active BOOLEAN, 
	is_verified BOOLEAN, 
	created_at DATETIME, 
	updated_at DATETIME, profile_photo_url VARCHAR(500), 
	PRIMARY KEY (id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id)
);

CREATE TABLE utility_bills (
	id INTEGER NOT NULL, 
	utility_id INTEGER NOT NULL, 
	billing_period_start DATE, 
	billing_period_end DATE, 
	due_date DATE, 
	amount NUMERIC(10, 2) NOT NULL, 
	paid_at DATE, 
	invoice_url VARCHAR(500), 
	notes TEXT, 
	created_by_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(utility_id) REFERENCES property_utilities (id), 
	FOREIGN KEY(created_by_id) REFERENCES users (id)
);

CREATE TABLE work_order_updates (
	id INTEGER NOT NULL, 
	work_order_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	from_status VARCHAR(12), 
	to_status VARCHAR(12), 
	message TEXT, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(work_order_id) REFERENCES work_orders (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE work_orders (
	id INTEGER NOT NULL, 
	unit_id INTEGER NOT NULL, 
	tenant_id INTEGER NOT NULL, 
	property_id INTEGER NOT NULL, 
	assigned_to_id INTEGER, 
	assigned_at DATETIME, 
	assigned_by_id INTEGER, 
	title VARCHAR(255) NOT NULL, 
	description TEXT NOT NULL, 
	category VARCHAR(11) NOT NULL, 
	priority VARCHAR(9) NOT NULL, 
	status VARCHAR(12) NOT NULL, 
	permission_to_enter BOOLEAN, 
	entry_notes TEXT, 
	photo_urls TEXT, 
	labor_cost NUMERIC(10, 2), 
	materials_cost NUMERIC(10, 2), 
	total_cost NUMERIC(10, 2), 
	resolution_notes TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	completed_at DATETIME, 
	closed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unit_id) REFERENCES units (id), 
	FOREIGN KEY(tenant_id) REFERENCES users (id), 
	FOREIGN KEY(property_id) REFERENCES properties (id), 
	FOREIGN KEY(assigned_to_id) REFERENCES users (id), 
	FOREIGN KEY(assigned_by_id) REFERENCES users (id)
);

CREATE INDEX ix_application_payments_applicant_user_id ON application_payments (applicant_user_id);

CREATE INDEX ix_application_payments_application_id ON application_payments (application_id);

CREATE INDEX ix_application_payments_id ON application_payments (id);

CREATE INDEX ix_application_payments_property_id ON application_payments (property_id);

CREATE INDEX ix_audit_log_created_at ON audit_log (created_at);

CREATE INDEX ix_audit_log_entity_id ON audit_log (entity_id);

CREATE INDEX ix_audit_log_entity_type ON audit_log (entity_type);

CREATE INDEX ix_audit_log_id ON audit_log (id);

CREATE INDEX ix_audit_log_organization_id ON audit_log (organization_id);

CREATE INDEX ix_audit_log_user_id ON audit_log (user_id);

CREATE INDEX ix_lease_applications_applicant_user_id ON lease_applications (applicant_user_id);

CREATE INDEX ix_lease_applications_id ON lease_applications (id);

CREATE INDEX ix_lease_applications_property_id ON lease_applications (property_id);

CREATE INDEX ix_lease_applications_unit_id ON lease_applications (unit_id);

CREATE INDEX ix_leases_id ON leases (id);

CREATE INDEX ix_leases_tenant_id ON leases (tenant_id);

CREATE INDEX ix_leases_unit_id ON leases (unit_id);

CREATE INDEX ix_organization_email_settings_id ON organization_email_settings (id);

CREATE UNIQUE INDEX ix_organization_email_settings_organization_id ON organization_email_settings (organization_id);

CREATE INDEX ix_organization_screening_settings_id ON organization_screening_settings (id);

CREATE UNIQUE INDEX ix_organization_screening_settings_organization_id ON organization_screening_settings (organization_id);

CREATE INDEX ix_organizations_id ON organizations (id);

CREATE UNIQUE INDEX ix_organizations_slug ON organizations (slug);

CREATE INDEX ix_password_reset_tokens_id ON password_reset_tokens (id);

CREATE UNIQUE INDEX ix_password_reset_tokens_token ON password_reset_tokens (token);

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE INDEX ix_payments_id ON payments (id);

CREATE INDEX ix_payments_invoice_id ON payments (invoice_id);

CREATE INDEX ix_platform_settings_id ON platform_settings (id);

CREATE UNIQUE INDEX ix_platform_settings_key ON platform_settings ("key");

CREATE INDEX ix_properties_id ON properties (id);

CREATE INDEX ix_properties_organization_id ON properties (organization_id);

CREATE INDEX ix_property_assignments_id ON property_assignments (id);

CREATE INDEX ix_property_assignments_property_id ON property_assignments (property_id);

CREATE INDEX ix_property_assignments_user_id ON property_assignments (user_id);

CREATE INDEX ix_property_expenses_id ON property_expenses (id);

CREATE INDEX ix_property_expenses_property_id ON property_expenses (property_id);

CREATE INDEX ix_property_income_id ON property_income (id);

CREATE INDEX ix_property_income_property_id ON property_income (property_id);

CREATE INDEX ix_property_insurance_id ON property_insurance (id);

CREATE INDEX ix_property_insurance_property_id ON property_insurance (property_id);

CREATE INDEX ix_property_tax_payments_id ON property_tax_payments (id);

CREATE INDEX ix_property_tax_payments_tax_id ON property_tax_payments (tax_id);

CREATE INDEX ix_property_taxes_id ON property_taxes (id);

CREATE INDEX ix_property_taxes_property_id ON property_taxes (property_id);

CREATE INDEX ix_property_utilities_id ON property_utilities (id);

CREATE INDEX ix_property_utilities_property_id ON property_utilities (property_id);

CREATE INDEX ix_rent_invoices_id ON rent_invoices (id);

CREATE INDEX ix_rent_invoices_lease_id ON rent_invoices (lease_id);

CREATE INDEX ix_screening_providers_id ON screening_providers (id);

CREATE INDEX ix_sidebar_preferences_id ON sidebar_preferences (id);

CREATE UNIQUE INDEX ix_sidebar_preferences_organization_id ON sidebar_preferences (organization_id);

CREATE INDEX ix_tenant_insurance_id ON tenant_insurance (id);

CREATE INDEX ix_tenant_insurance_lease_id ON tenant_insurance (lease_id);

CREATE INDEX ix_tenant_insurance_property_id ON tenant_insurance (property_id);

CREATE INDEX ix_tenant_insurance_tenant_id ON tenant_insurance (tenant_id);

CREATE INDEX ix_trash_pickup_schedule_id ON trash_pickup_schedule (id);

CREATE INDEX ix_trash_pickup_schedule_property_id ON trash_pickup_schedule (property_id);

CREATE INDEX ix_units_id ON units (id);

CREATE INDEX ix_units_property_id ON units (property_id);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_users_id ON users (id);

CREATE INDEX ix_users_organization_id ON users (organization_id);

CREATE INDEX ix_utility_bills_id ON utility_bills (id);

CREATE INDEX ix_utility_bills_utility_id ON utility_bills (utility_id);

CREATE INDEX ix_work_order_updates_id ON work_order_updates (id);

CREATE INDEX ix_work_order_updates_user_id ON work_order_updates (user_id);

CREATE INDEX ix_work_order_updates_work_order_id ON work_order_updates (work_order_id);

CREATE INDEX ix_work_orders_assigned_to_id ON work_orders (assigned_to_id);

CREATE INDEX ix_work_orders_id ON work_orders (id);

CREATE INDEX ix_work_orders_property_id ON work_orders (property_id);

CREATE INDEX ix_work_orders_tenant_id ON work_orders (tenant_id);

CREATE INDEX ix_work_orders_unit_id ON work_orders (unit_id);

CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num));

INSERT INTO alembic_version(version_num) VALUES ('1d77e94a0fb5');

PRAGMA foreign_keys=ON;
