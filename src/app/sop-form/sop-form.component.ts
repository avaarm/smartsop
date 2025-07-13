import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { AIService, DocumentRequest } from '../services/ai-service.service';

@Component({
  selector: 'app-sop-form',
  standalone: true,
  imports: [FormsModule, CommonModule],
  template: `
    <div class="container mx-auto p-4 max-w-2xl">
      <h1 class="text-2xl font-bold mb-6">Generate SOP or Batch Record</h1>
      
      <form (ngSubmit)="onSubmit()" #form="ngForm" class="space-y-4">
        <div class="form-group">
          <label class="block text-sm font-medium mb-2">Document Type</label>
          <select [(ngModel)]="formData.type" name="type" class="w-full p-2 border rounded">
            <option value="sop">Standard Operating Procedure (SOP)</option>
            <option value="batch">Batch Record</option>
          </select>
        </div>

        <div class="form-group">
          <label class="block text-sm font-medium mb-2">Process Steps</label>
          <textarea
            [(ngModel)]="formData.steps"
            name="steps"
            required
            rows="4"
            class="w-full p-2 border rounded"
            placeholder="Enter the process steps..."
          ></textarea>
        </div>

        <div class="form-group">
          <label class="block text-sm font-medium mb-2">Roles Involved</label>
          <textarea
            [(ngModel)]="formData.roles"
            name="roles"
            required
            rows="2"
            class="w-full p-2 border rounded"
            placeholder="List the roles involved..."
          ></textarea>
        </div>

        <div class="form-group">
          <label class="block text-sm font-medium mb-2">Additional Notes</label>
          <textarea
            [(ngModel)]="formData.notes"
            name="notes"
            rows="2"
            class="w-full p-2 border rounded"
            placeholder="Any additional requirements or notes..."
          ></textarea>
        </div>

        <button
          type="submit"
          [disabled]="loading || !form.form.valid"
          class="w-full bg-blue-500 text-white p-2 rounded hover:bg-blue-600 disabled:bg-gray-400"
        >
          {{ loading ? 'Generating...' : 'Generate Document' }}
        </button>
      </form>

      <div *ngIf="errorMessage" class="mt-4 p-4 bg-red-100 text-red-700 rounded">
        {{ errorMessage }}
      </div>

      <div *ngIf="generatedContent" class="mt-4">
        <h2 class="text-xl font-bold mb-2">Generated {{ formData.type === 'sop' ? 'SOP' : 'Batch Record' }}</h2>
        <div class="p-4 bg-gray-50 rounded whitespace-pre-wrap">
          {{ generatedContent }}
        </div>

        <!-- Feedback Section -->
        <div *ngIf="!feedbackSubmitted" class="mt-4 p-4 bg-blue-50 rounded">
          <h3 class="text-lg font-semibold mb-3">Provide Feedback</h3>
          <p class="text-sm text-gray-600 mb-4">Your feedback helps improve the quality of generated documents.</p>
          
          <div class="mb-4">
            <label class="block text-sm font-medium mb-2">Quality Rating</label>
            <div class="flex gap-2">
              <button
                *ngFor="let score of [1,2,3,4,5]"
                (click)="selectRating(score)"
                [class.bg-blue-500]="selectedRating === score"
                [class.text-white]="selectedRating === score"
                class="px-4 py-2 rounded border hover:bg-blue-100"
              >
                {{score}}
              </button>
            </div>
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium mb-2">Comments (Optional)</label>
            <textarea
              [(ngModel)]="feedbackText"
              name="feedbackText"
              rows="2"
              class="w-full p-2 border rounded"
              placeholder="Any suggestions for improvement?"
            ></textarea>
          </div>

          <button
            (click)="submitFeedback()"
            [disabled]="!selectedRating || submittingFeedback"
            class="w-full bg-green-500 text-white p-2 rounded hover:bg-green-600 disabled:bg-gray-400"
          >
            {{ submittingFeedback ? 'Submitting...' : 'Submit Feedback' }}
          </button>
        </div>

        <div *ngIf="feedbackSubmitted" class="mt-4 p-4 bg-green-50 rounded">
          <p class="text-green-700">Thank you for your feedback! Your input helps improve the system.</p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .form-group { margin-bottom: 1rem; }
    textarea, select { width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }
    button { transition: all 0.2s; }
    button:disabled { cursor: not-allowed; }
  `]
})
export class SopFormComponent {
  formData: DocumentRequest = {
    steps: '',
    roles: '',
    notes: '',
    type: 'sop'
  };
  generatedContent: string = '';
  errorMessage: string = '';
  loading: boolean = false;

  // Feedback related properties
  selectedRating: number | null = null;
  feedbackText: string = '';
  feedbackSubmitted: boolean = false;
  submittingFeedback: boolean = false;
  currentDocId: string = '';

  constructor(private aiService: AIService) {}

  onSubmit() {
    this.errorMessage = '';
    this.generatedContent = '';
    this.loading = true;
    this.feedbackSubmitted = false;
    this.selectedRating = null;
    this.feedbackText = '';

    this.aiService.generateDocument(this.formData).subscribe({
      next: (response) => {
        if (response.success) {
          this.generatedContent = response.content;
          this.currentDocId = response.doc_id;
        } else {
          this.errorMessage = response.error || 'Failed to generate document';
        }
        this.loading = false;
      },
      error: (error) => {
        this.errorMessage = 'An error occurred while generating the document. Please try again.';
        this.loading = false;
        console.error('Error:', error);
      }
    });
  }

  selectRating(score: number) {
    this.selectedRating = score;
  }

  submitFeedback() {
    if (!this.selectedRating) return;

    this.submittingFeedback = true;
    
    this.aiService.submitFeedback({
      doc_id: this.currentDocId,
      score: this.selectedRating,
      text: this.feedbackText
    }).subscribe({
      next: (response) => {
        if (response.success) {
          this.feedbackSubmitted = true;
        } else {
          this.errorMessage = 'Failed to submit feedback';
        }
        this.submittingFeedback = false;
      },
      error: (error) => {
        this.errorMessage = 'An error occurred while submitting feedback';
        this.submittingFeedback = false;
        console.error('Error:', error);
      }
    });
  }
}







