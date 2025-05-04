# SmartSOP

SmartSOP is an intelligent document generation tool that helps create Standard Operating Procedures (SOPs) and Batch Records using AI. Built with Angular and Python, it leverages GPT-4 to generate professionally formatted documents based on user input.

## Features

- Generate detailed Standard Operating Procedures (SOPs)
- Create comprehensive Batch Records
- AI-powered document formatting
- User-friendly interface
- Real-time document generation
- Professional document structure

## Prerequisites

Before you begin, ensure you have the following installed:
- Node.js (v18 or higher)
- Python (v3.8 or higher)
- Angular CLI
- OpenAI API key

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/smartsop.git
cd smartsop
```

2. Install frontend dependencies:
```bash
npm install
```

3. Install backend dependencies:
```bash
pip install flask flask-cors python-dotenv openai
```

4. Create a `.env` file in the root directory and add your OpenAI API key:
```
OPENAI_API_KEY=your_api_key_here
```

## Running the Application

1. Start the Python backend:
```bash
python app.py
```

2. In a new terminal, start the Angular frontend:
```bash
npm start
```

3. Open your browser and navigate to `http://localhost:4200`

## Using SmartSOP

1. Select Document Type:
   - Choose between SOP or Batch Record

2. Enter Process Information:
   - Process Steps: Detail the steps of your procedure
   - Roles Involved: List all roles and responsibilities
   - Additional Notes: Add any special requirements or considerations

3. Generate Document:
   - Click 'Generate Document' to create your document
   - The AI will process your input and generate a professionally formatted document

## Document Structure

### SOPs include:
- Purpose
- Scope
- Responsibilities
- Safety Precautions
- Required Materials
- Detailed Procedure Steps
- Quality Control
- Documentation Requirements

### Batch Records include:
- Batch Identification
- Material Information
- Equipment Setup Verification
- Process Steps with Sign-offs
- In-Process Controls
- Quality Checks
- Deviation Recording
- Final Product Details

## Technology Stack

- Frontend: Angular 18
- Backend: Flask (Python)
- AI: OpenAI GPT-4
- API: RESTful architecture
- Styling: Modern CSS with responsive design

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the development team.

## Development server

Run `ng serve` for a dev server. Navigate to `http://localhost:4200/`. The application will automatically reload if you change any of the source files.

## Code scaffolding

Run `ng generate component component-name` to generate a new component. You can also use `ng generate directive|pipe|service|class|guard|interface|enum|module`.

## Build

Run `ng build` to build the project. The build artifacts will be stored in the `dist/` directory.

## Running unit tests

Run `ng test` to execute the unit tests via [Karma](https://karma-runner.github.io).

## Running end-to-end tests

Run `ng e2e` to execute the end-to-end tests via a platform of your choice. To use this command, you need to first add a package that implements end-to-end testing capabilities.

## Further help

To get more help on the Angular CLI use `ng help` or go check out the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
