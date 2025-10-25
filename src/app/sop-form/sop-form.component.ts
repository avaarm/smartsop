import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { AIService, DocumentRequest } from '../services/ai-service.service';

@Component({
  selector: 'app-sop-form',
  standalone: true,
  imports: [FormsModule, CommonModule],
  templateUrl: './sop-form.component.html',
  styleUrls: ['./sop-form.component.scss']
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
