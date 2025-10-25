import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute, Router } from '@angular/router';
import { FormBuilder, FormGroup, Validators, ReactiveFormsModule } from '@angular/forms';
import { ElnService, Experiment, Protocol } from '../../../../services/eln-service.service';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialogModule } from '@angular/material/dialog';

@Component({
  selector: 'app-experiment-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    ReactiveFormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatTabsModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatTableModule,
    MatExpansionModule,
    MatChipsModule,
    MatDialogModule
  ],
  providers: [MatSnackBar],
  templateUrl: './experiment-detail.component.html',
  styleUrls: ['./experiment-detail.component.scss']
})
export class ExperimentDetailComponent implements OnInit {
  experimentId: string | null = null;
  experiment: Experiment | null = null;
  experimentForm: FormGroup;
  isNewExperiment = false;
  loading = true;
  saving = false;
  error = '';
  editMode = false;
  
  // Project selection
  projects: { id: string, name: string }[] = [];
  selectedProjectId: string | null = null;
  
  // Protocols
  protocols: Protocol[] = [];
  selectedProtocolId: string | null = null;
  
  // Results and notes
  resultsData: any[] = [];

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private elnService: ElnService,
    private fb: FormBuilder,
    private snackBar: MatSnackBar
  ) {
    this.experimentForm = this.fb.group({
      name: ['', [Validators.required]],
      description: ['', [Validators.required]],
      project_id: [''],
      protocol_id: [''],
      status: ['active', [Validators.required]],
      start_date: [null],
      end_date: [null],
      hypothesis: [''],
      materials: [''],
      methods: [''],
      results_summary: [''],
      conclusion: ['']
    });
  }

  ngOnInit(): void {
    this.loadProjects();
    
    this.route.paramMap.subscribe(params => {
      this.experimentId = params.get('id');
      
      if (this.experimentId === 'new') {
        this.isNewExperiment = true;
        this.editMode = true;
        this.loading = false;
        
        // Check if there's a project ID in the query params
        this.route.queryParams.subscribe(queryParams => {
          if (queryParams['projectId']) {
            this.selectedProjectId = queryParams['projectId'];
            this.experimentForm.patchValue({
              project_id: this.selectedProjectId
            });
          }
        });
      } else if (this.experimentId) {
        this.loadExperiment();
      }
    });
  }

  loadExperiment(): void {
    if (!this.experimentId) return;
    
    this.loading = true;
    this.elnService.getExperiment(this.experimentId).subscribe({
      next: (response) => {
        if (response.success && response.experiment) {
          this.experiment = response.experiment;
          this.selectedProjectId = this.experiment.project_id || null;
          this.selectedProtocolId = (this.experiment as any).protocol_id || null;
          this.populateForm();
          
          // Load protocols if project is selected
          if (this.selectedProjectId) {
            this.loadProtocols(this.selectedProjectId);
          }
          
          // Load experiment results
          this.loadExperimentResults();
        } else {
          this.error = response.error || 'Failed to load experiment';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load experiment';
        this.loading = false;
      }
    });
  }

  loadProjects(): void {
    this.elnService.getProjects().subscribe({
      next: (response) => {
        if (response.success && response.projects) {
          this.projects = response.projects.map(project => ({
            id: project.id,
            name: project.name
          }));
        }
      },
      error: (err) => {
        console.error('Failed to load projects:', err);
      }
    });
  }

  loadProtocols(projectId: string): void {
    this.elnService.getProtocols().subscribe({
      next: (response: any) => {
        if (response.success && response.protocols) {
          this.protocols = response.protocols;
        }
      },
      error: (err: any) => {
        console.error('Failed to load protocols:', err);
      }
    });
  }

  loadExperimentResults(): void {
    if (!this.experimentId) return;
    
    // TODO: Implement getExperimentResults in ElnService
    console.log('Experiment results feature coming soon');
    
    /* this.elnService.getExperimentResults(this.experimentId).subscribe({
      next: (response: any) => {
        if (response.success && response.results) {
          this.resultsData = response.results;
        }
      },
      error: (err: any) => {
        console.error('Failed to load experiment results:', err);
      }
    }); */
  }

  populateForm(): void {
    if (!this.experiment) return;
    
    this.experimentForm.patchValue({
      name: this.experiment.name,
      description: this.experiment.description,
      project_id: this.experiment.project_id || '',
      protocol_id: (this.experiment as any).protocol_id || '',
      status: this.experiment.status,
      start_date: this.experiment.start_date ? new Date(this.experiment.start_date) : null,
      end_date: this.experiment.end_date ? new Date(this.experiment.end_date) : null,
      hypothesis: this.experiment.hypothesis || '',
      materials: (this.experiment as any).materials || '',
      methods: (this.experiment as any).methods || '',
      results_summary: (this.experiment as any).results_summary || '',
      conclusion: (this.experiment as any).conclusion || ''
    });
  }

  toggleEditMode(): void {
    this.editMode = !this.editMode;
    if (!this.editMode) {
      this.populateForm();
    }
  }

  onProjectChange(projectId: string): void {
    if (projectId) {
      this.loadProtocols(projectId);
    } else {
      this.protocols = [];
      this.experimentForm.patchValue({
        protocol_id: ''
      });
    }
  }

  saveExperiment(): void {
    if (this.experimentForm.invalid) {
      this.experimentForm.markAllAsTouched();
      return;
    }
    
    const experimentData = {
      ...this.experimentForm.value,
      start_date: this.experimentForm.value.start_date ? this.formatDate(this.experimentForm.value.start_date) : null,
      end_date: this.experimentForm.value.end_date ? this.formatDate(this.experimentForm.value.end_date) : null
    };
    
    this.saving = true;
    
    if (this.isNewExperiment) {
      this.elnService.createExperiment(experimentData).subscribe({
        next: (response) => {
          if (response.success && response.experiment) {
            this.snackBar.open('Experiment created successfully', 'Close', {
              duration: 3000
            });
            this.router.navigate(['/eln/experiments', response.experiment.id]);
          } else {
            this.snackBar.open(response.error || 'Failed to create experiment', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to create experiment', 'Close', {
            duration: 5000
          });
          this.saving = false;
        }
      });
    } else if (this.experimentId) {
      this.elnService.updateExperiment(this.experimentId, experimentData).subscribe({
        next: (response) => {
          if (response.success && response.experiment) {
            this.experiment = response.experiment;
            this.editMode = false;
            this.snackBar.open('Experiment updated successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to update experiment', 'Close', {
              duration: 5000
            });
          }
          this.saving = false;
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to update experiment', 'Close', {
            duration: 5000
          });
          this.saving = false;
        }
      });
    }
  }

  formatDate(date: Date): string {
    return date.toISOString().split('T')[0];
  }

  addResult(): void {
    this.router.navigate(['/eln/experiments', this.experimentId, 'results', 'new']);
  }

  getStatusClass(status: string): string {
    switch (status.toLowerCase()) {
      case 'active':
        return 'status-active';
      case 'completed':
        return 'status-completed';
      case 'on hold':
        return 'status-on-hold';
      case 'in progress':
        return 'status-active';
      default:
        return 'status-default';
    }
  }

  generateReport(): void {
    if (!this.experimentId) return;
    
    // TODO: Implement generateExperimentReport in ElnService
    this.snackBar.open('Report generation feature coming soon', 'Close', {
      duration: 3000
    });
    
    /* this.elnService.generateExperimentReport(this.experimentId).subscribe({
      next: (response: any) => {
        if (response.success) {
          this.snackBar.open('Report generated successfully', 'Close', {
            duration: 3000
          });
          
          // Open the report in a new window or download it
          if (response.report_url) {
            window.open(response.report_url, '_blank');
          }
        } else {
          this.snackBar.open(response.error || 'Failed to generate report', 'Close', {
            duration: 5000
          });
        }
      },
      error: (err: any) => {
        this.snackBar.open(err.message || 'Failed to generate report', 'Close', {
          duration: 5000
        });
      }
    }); */
  }
}
