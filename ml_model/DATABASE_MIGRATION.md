# SmartSOP to ELN Database Migration

This document provides instructions for migrating from the file-based JSON storage system of SmartSOP to the new relational database structure for the AI/LLM-powered scientific electronic lab notebook (ELN).

## Database Schema Overview

The new database schema includes the following core entities:

- **Project**: Top-level container for research work
- **Experiment**: Individual experiments within a project
- **Task**: Specific tasks within an experiment
- **Protocol**: Step-by-step procedures for experiments
- **InventoryItem**: Lab supplies, reagents, and equipment
- **User**: System users with different roles and permissions

Additional entities include:
- Comments
- Audit logs
- Electronic signatures
- Experiment data
- Protocol steps
- Inventory usage tracking

## Migration Process

The migration process consists of two main steps:

1. **Initialize the database**: Create all tables in the new relational database
2. **Migrate data**: Transfer data from JSON files to the new database structure

### Prerequisites

- Python 3.7+
- SQLAlchemy
- Required Python packages (install with `pip install -r requirements.txt`)

### Step 1: Initialize the Database

Run the database initialization script to create all tables:

```bash
cd /Users/armenuhi/Programming/smartsop
python -m ml_model.init_db
```

This will create a SQLite database file (`smartsop.db`) in the root directory. For production, you can configure a different database by setting the `DATABASE_URL` environment variable.

### Step 2: Migrate Data

Run the data migration script to transfer data from JSON files to the new database:

```bash
cd /Users/armenuhi/Programming/smartsop
python -m ml_model.migrate_data
```

This script will:
1. Create a default admin user if none exists
2. Create projects for migrated SOPs and batch records
3. Convert SOP documents to protocols and experiments
4. Preserve all metadata, feedback, and content from the original files
5. Create audit logs for the migration process

## Verification

After migration, you can verify the data by:

1. Checking the database tables for expected records
2. Comparing the original JSON files with the migrated data
3. Running the application with the new database

## Rollback

If needed, you can roll back the migration by:

1. Deleting the database file (if using SQLite)
2. Restoring any backup of the original JSON files

## Next Steps

After successful migration:

1. Update the application code to use the new database models
2. Implement the new API endpoints for the ELN functionality
3. Develop the updated UI components

## Troubleshooting

If you encounter issues during migration:

- Check the log output for specific error messages
- Verify that all JSON files are properly formatted
- Ensure all required directories exist
- Check database permissions

For additional help, contact the development team.
