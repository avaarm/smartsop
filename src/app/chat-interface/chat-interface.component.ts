import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { AIService } from '../services/ai-service.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  docId?: string;
  showFeedback?: boolean;
  wordDocument?: {
    filename: string;
    downloadUrl: string;
  };
}

interface DocumentType {
  id: 'sop' | 'batch';
  name: string;
}

interface DocumentRequest {
  steps: string;
  roles: string;
  type: 'sop' | 'batch';
}

@Component({
  selector: 'app-chat-interface',
  standalone: true,
  imports: [FormsModule, CommonModule],
  templateUrl: './chat-interface.component.html',
  styleUrls: ['./chat-interface.component.scss']
})
export class ChatInterfaceComponent implements OnInit {
  chatMessages: ChatMessage[] = [];
  newMessage: string = '';
  isLoading: boolean = false;
  documentType: 'sop' | 'batch' = 'sop';
  documentTypes: DocumentType[] = [
    { id: 'sop', name: 'Standard Operating Procedure (SOP)' },
    { id: 'batch', name: 'Batch Record' }
  ];
  feedbackRating: number | null = null;
  feedbackText: string = '';
  showFeedback: boolean = false;
  feedbackSubmitted: boolean = false;

  constructor(private aiService: AIService) { }

  ngOnInit(): void {
    // Add welcome message
    this.chatMessages.push({
      role: 'assistant',
      content: 'Hello! I\'m your SOP and Batch Record assistant. How can I help you today? You can ask me to create a document or provide information about SOPs and Batch Records.',
      timestamp: new Date()
    });
  }

  sendMessage(): void {
    if (!this.newMessage.trim()) return;

    // Add user message to chat
    const userMessage: ChatMessage = {
      role: 'user',
      content: this.newMessage,
      timestamp: new Date()
    };
    this.chatMessages.push(userMessage);

    // Clear input field
    const messageToSend = this.newMessage;
    this.newMessage = '';

    // Show loading indicator
    this.isLoading = true;

    // Prepare request to AI service
    const request: DocumentRequest = {
      steps: messageToSend,
      roles: 'All relevant personnel',
      type: this.documentType
    };

    // Send request to AI service
    this.aiService.generateDocument(request).subscribe({
      next: (response) => {
        // Add AI response to chat
        const aiMessage: ChatMessage = {
          role: 'assistant',
          content: response.content,
          timestamp: new Date(),
          docId: response.doc_id,
          showFeedback: true
        };

        // Add Word document info if available
        if (response.word_document) {
          aiMessage.wordDocument = {
            filename: response.word_document.filename,
            downloadUrl: `http://localhost:5000${response.word_document.download_url}`
          };
        }

        this.chatMessages.push(aiMessage);
        this.isLoading = false;
      },
      error: (error) => {
        console.error('Error generating document:', error);
        // Add error message to chat
        const errorMessage: ChatMessage = {
          role: 'assistant',
          content: 'Sorry, I encountered an error while generating the document. Please try again.',
          timestamp: new Date()
        };
        this.chatMessages.push(errorMessage);
        this.isLoading = false;
      }
    });
  }

  setDocumentType(type: 'sop' | 'batch'): void {
    this.documentType = type;
  }

  setFeedbackRating(rating: number): void {
    this.feedbackRating = rating;
  }

  submitFeedback(docId: string): void {
    if (this.feedbackRating === null || !docId) return;

    this.aiService.submitFeedback({
      doc_id: docId,
      score: this.feedbackRating,
      text: this.feedbackText
    }).subscribe({
      next: (response) => {
        if (response.success) {
          this.feedbackSubmitted = true;
          this.showFeedback = false;
          
          // Add a thank you message
          this.chatMessages.push({
            role: 'assistant',
            content: 'Thank you for your feedback! Is there anything else I can help you with?',
            timestamp: new Date()
          });
          
          // Reset feedback form
          this.feedbackRating = null;
          this.feedbackText = '';
        }
      },
      error: (error) => {
        console.error('Error submitting feedback:', error);
      }
    });
  }

  // Helper method to format timestamps
  formatTime(date: Date): string {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  handleKeyDown(event: KeyboardEvent): void {
    // Only handle Enter key
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }
}
