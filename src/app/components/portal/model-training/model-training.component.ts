import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AIService, TrainingMetrics, ModelStats } from '../../../services/ai-service.service';
import { interval, Subscription } from 'rxjs';
import { switchMap } from 'rxjs/operators';

// Interface for advanced training options
interface TrainingOptions {
  numEpochs: number;
  learningRate: number;
  batchSize: number;
  useGradientCheckpointing: boolean;
  earlyStoppingPatience: number;
}

@Component({
  selector: 'app-model-training',
  templateUrl: './model-training.component.html',
  styleUrls: ['./model-training.component.scss'],
  imports: [CommonModule, FormsModule, DecimalPipe],
  standalone: true
})
export class ModelTrainingComponent implements OnInit, OnDestroy {
  // Training parameters
  minFeedbackScore: number = 3.5;
  minExamples: number = 10;
  
  // Advanced training options
  showAdvancedOptions: boolean = false;
  trainingOptions: TrainingOptions = {
    numEpochs: 5,
    learningRate: 0.00002, // 2e-5
    batchSize: 2,
    useGradientCheckpointing: true,
    earlyStoppingPatience: 3
  };
  
  // Training status
  isTrainingInProgress: boolean = false;
  trainingHistory: TrainingMetrics[] = [];
  latestModel: string | null = null;
  selectedTraining: TrainingMetrics | null = null;
  
  // Stats
  stats: ModelStats | null = null;
  
  // Error handling
  error: string | null = null;
  successMessage: string | null = null;
  
  // Status polling
  private statusSubscription: Subscription | null = null;
  
  constructor(private aiService: AIService) {}
  
  ngOnInit(): void {
    // Load initial data
    this.loadTrainingStatus();
    this.loadStats();
  }
  
  ngOnDestroy(): void {
    // Clean up subscriptions
    if (this.statusSubscription) {
      this.statusSubscription.unsubscribe();
    }
  }
  
  loadTrainingStatus(): void {
    this.aiService.getTrainingStatus().subscribe({
      next: (response) => {
        if (response.success) {
          this.trainingHistory = response.training_history;
          this.isTrainingInProgress = response.is_training_in_progress;
          this.latestModel = response.latest_model;
          
          // If training is in progress, start polling for updates
          if (this.isTrainingInProgress && !this.statusSubscription) {
            this.startStatusPolling();
          } else if (!this.isTrainingInProgress && this.statusSubscription) {
            // Stop polling if training is complete
            this.statusSubscription.unsubscribe();
            this.statusSubscription = null;
          }
        } else {
          this.error = response.error || 'Failed to load training status';
        }
      },
      error: (err) => {
        this.error = err.message || 'Error loading training status';
      }
    });
  }
  
  loadStats(): void {
    this.aiService.getModelStats().subscribe({
      next: (response) => {
        if (response.success) {
          this.stats = response.stats;
        } else {
          this.error = response.error || 'Failed to load model statistics';
        }
      },
      error: (err) => {
        this.error = err.message || 'Error loading model statistics';
      }
    });
  }
  
  startTraining(): void {
    this.error = null;
    this.successMessage = null;
    
    // Include advanced training options if they're shown
    const trainingParams: any = {
      min_feedback_score: this.minFeedbackScore,
      min_examples: this.minExamples
    };
    
    if (this.showAdvancedOptions) {
      trainingParams.advanced_options = {
        num_epochs: this.trainingOptions.numEpochs,
        learning_rate: this.trainingOptions.learningRate,
        batch_size: this.trainingOptions.batchSize,
        use_gradient_checkpointing: this.trainingOptions.useGradientCheckpointing,
        early_stopping_patience: this.trainingOptions.earlyStoppingPatience
      };
    }
    
    this.aiService.triggerTraining(trainingParams).subscribe({
      next: (response) => {
        if (response.success) {
          this.successMessage = response.message || 'Training started successfully';
          this.isTrainingInProgress = true;
          this.startStatusPolling();
        } else {
          this.error = response.error || 'Failed to start training';
        }
      },
      error: (err) => {
        this.error = err.message || 'Error starting training';
      }
    });
  }
  
  toggleAdvancedOptions(): void {
    this.showAdvancedOptions = !this.showAdvancedOptions;
  }
  
  selectTrainingRun(training: TrainingMetrics): void {
    this.selectedTraining = training;
  }
  
  formatDuration(seconds?: number): string {
    if (!seconds) return 'N/A';
    
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    
    if (minutes === 0) {
      return `${remainingSeconds}s`;
    } else {
      return `${minutes}m ${remainingSeconds}s`;
    }
  }
  
  private startStatusPolling(): void {
    // Poll every 5 seconds
    if (this.statusSubscription) {
      this.statusSubscription.unsubscribe();
    }
    
    this.statusSubscription = interval(5000).pipe(
      switchMap(() => this.aiService.getTrainingStatus())
    ).subscribe({
      next: (response) => {
        if (response.success) {
          this.trainingHistory = response.training_history;
          this.isTrainingInProgress = response.is_training_in_progress;
          this.latestModel = response.latest_model;
          
          // If training is complete, stop polling and refresh stats
          if (!this.isTrainingInProgress) {
            if (this.statusSubscription) {
              this.statusSubscription.unsubscribe();
              this.statusSubscription = null;
            }
            this.loadStats();
          }
        }
      },
      error: (err) => {
        console.error('Error polling training status:', err);
      }
    });
  }
  
  // Format date from timestamp string (YYYYMMDD_HHMMSS)
  formatDate(timestamp: string): string {
    if (!timestamp) return 'Unknown';
    
    try {
      const year = timestamp.substring(0, 4);
      const month = timestamp.substring(4, 6);
      const day = timestamp.substring(6, 8);
      const hour = timestamp.substring(9, 11);
      const minute = timestamp.substring(11, 13);
      const second = timestamp.substring(13, 15);
      
      return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
    } catch (e) {
      return timestamp;
    }
  }
}
