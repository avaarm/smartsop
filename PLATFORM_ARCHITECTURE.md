# SmartSOP Lab Platform Architecture

## Overview
Comprehensive laboratory management platform combining AI-powered SOP generation with full Electronic Lab Notebook (ELN) capabilities.

## Architecture

### Frontend (Angular 18)
- **Framework:** Angular 18 with standalone components
- **State Management:** RxJS observables
- **Routing:** Lazy-loaded modules for optimal performance
- **UI Pattern:** Sidebar navigation with nested routes

### Backend (Flask + Python)
- **Web Framework:** Flask with CORS support
- **AI Model:** Microsoft Phi-2 (fine-tunable)
- **Database:** SQLAlchemy ORM with PostgreSQL/SQLite
- **Document Processing:** Multi-format export (Word, PDF, Excel, CSV)

## Feature Modules

### 1. Document Generation
- **AI Chat Interface:** Conversational SOP creation
- **Form-Based Generation:** Structured input for SOPs and Batch Records
- **Multi-Format Export:**
  - Word (.docx) - Fully formatted with styles
  - PDF - Print-ready with professional layout
  - Excel (.xlsx) - Structured sections in spreadsheets
  - CSV - Flat file format for data processing

### 2. ELN Modules

#### Projects Management
- Create and manage research projects
- Track project status and timeline
- Team member assignment and roles
- **Routes:** `/eln/projects`, `/eln/projects/:id`

#### Experiments
- Design and document experiments
- Track hypothesis and methodology
- Link to protocols and inventory
- Record results and observations
- **Routes:** `/eln/experiments`, `/eln/experiments/:id`

#### Protocols
- Create standardized protocols
- Version control for protocol revisions
- Step-by-step procedures with parameters
- Assign protocols to experiments
- **Routes:** `/eln/protocols`, `/eln/protocols/:id`

#### Inventory Management
- Track lab materials and reagents
- Monitor stock levels with alerts
- Expiration date tracking
- Purchase history and suppliers
- **Routes:** `/eln/inventory`, `/eln/inventory/:id`

#### User Management
- User roles and permissions
- Activity tracking
- Project assignments
- Department organization
- **Routes:** `/eln/users`, `/eln/users/:id`

### 3. Model Training Portal
- View training statistics
- Trigger model fine-tuning
- Monitor training progress
- Review feedback data
- **Route:** `/training`

## Multi-Level Document Support

### Document Structure
SOPs are parsed into hierarchical sections:
```
1. PURPOSE
   1.1 Subsection
   1.2 Subsection
2. SCOPE
3. PROCEDURE
   3.1 Preparation
   3.2 Execution
   3.3 Clean-up
```

### Export Features
- **Section-based parsing** for structured exports
- **Metadata preservation** across all formats
- **Batch processing** capabilities for multiple documents

## Performance Optimizations

### Frontend
1. **Lazy Loading:** ELN modules load on-demand
2. **Route Guards:** Authentication and authorization checks
3. **Virtual Scrolling:** For large document lists (planned)
4. **Caching:** API responses cached for 5 minutes

### Backend
1. **Connection Pooling:** Efficient database connections
2. **Background Processing:** Model training runs asynchronously
3. **File Streaming:** Large document downloads use streaming
4. **Request Timeout:** 60-second timeout with retry logic

## LLM Integration

### Current Implementation
- **Model:** Microsoft Phi-2 (2.7B parameters)
- **Inference:** CPU/GPU support via PyTorch
- **Fine-tuning:** LoRA adapters for memory efficiency
- **Context Window:** 2048 tokens

### Handling Large Outputs
1. **Chunking:** Break large documents into sections
2. **Streaming:** Real-time token generation (planned)
3. **Pagination:** Client-side pagination for long content
4. **Progress Indicators:** Loading states during generation

## API Endpoints

### Document Generation
```
POST /api/generate_document
POST /api/export/<format>  (pdf|excel|csv)
GET  /api/export/formats
GET  /api/download/<filename>
```

### Training & Feedback
```
POST /api/feedback
POST /api/train
GET  /api/training/status
GET  /api/stats
```

### ELN Endpoints
```
Projects:    /api/projects, /api/projects/:id
Experiments: /api/experiments, /api/experiments/:id
Protocols:   /api/protocols, /api/protocols/:id
Inventory:   /api/inventory, /api/inventory/:id
Users:       /api/users, /api/users/:id
```

## Database Schema

### Core Tables
- **projects:** Research project metadata
- **experiments:** Experiment documentation
- **protocols:** Standardized procedures
- **inventory_items:** Lab materials tracking
- **users:** User accounts and roles
- **generated_documents:** SOP generation history
- **training_feedback:** Model improvement data

## Security Features

1. **Audit Logging:** All operations tracked
2. **Data Sanitization:** PII and sensitive data removal
3. **CORS Configuration:** Restricted origins
4. **File Validation:** Prevent path traversal attacks
5. **Encryption:** Sensitive data encrypted at rest

## Deployment

### Development
```bash
# Backend (port 5001)
python app.py --port=5001

# Frontend (port 4200)
npm start
```

### Production Considerations
1. Use production WSGI server (Gunicorn/uWSGI)
2. Enable HTTPS with SSL certificates
3. Use production database (PostgreSQL)
4. Configure environment variables
5. Set up monitoring and logging

## Future Enhancements

### Planned Features
1. **Real-time Collaboration:** Multi-user editing
2. **WebSocket Support:** Streaming LLM responses
3. **Advanced Search:** Full-text search across all documents
4. **Data Visualization:** Charts and graphs for experiments
5. **Mobile App:** React Native companion app
6. **API Rate Limiting:** Prevent abuse
7. **Document Versioning:** Git-like version control
8. **Template Library:** Reusable SOP templates

### Scalability Roadmap
1. **Microservices:** Split backend into services
2. **Message Queue:** Redis/RabbitMQ for async tasks
3. **Caching Layer:** Redis for API responses
4. **CDN Integration:** Static asset delivery
5. **Load Balancing:** Multiple backend instances

## Technology Stack

### Frontend
- Angular 18
- RxJS 7.8
- TypeScript 5.5
- Angular Material 20

### Backend
- Flask
- SQLAlchemy
- PyTorch
- Transformers (Hugging Face)
- python-docx, openpyxl, pandas, reportlab

### Development Tools
- Angular CLI
- Python venv
- Git version control
- VS Code / WebStorm

## License
MIT License - See LICENSE file for details
