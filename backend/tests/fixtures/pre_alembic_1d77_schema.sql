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
