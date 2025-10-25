import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ElnService, Experiment } from '../../../../services/eln-service.service';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatSortModule, Sort } from '@angular/material/sort';

@Component({
  selector: 'app-experiment-list',
  standalone: true,
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatInputModule,
    MatFormFieldModule,
    MatSelectModule,
    MatProgressSpinnerModule,
    MatSnackBarModule,
    MatTableModule,
    MatPaginatorModule,
    MatSortModule
  ],
  providers: [MatSnackBar],
  templateUrl: './experiment-list.component.html',
  styleUrls: ['./experiment-list.component.scss']
})
export class ExperimentListComponent implements OnInit {
  experiments: Experiment[] = [];
  filteredExperiments: Experiment[] = [];
  displayedExperiments: Experiment[] = [];
  loading = true;
  error = '';
  
  // Filter options
  statusFilter = 'all';
  projectFilter = 'all';
  searchQuery = '';
  
  // Pagination
  pageSize = 10;
  pageSizeOptions = [5, 10, 25, 50];
  pageIndex = 0;
  totalExperiments = 0;
  
  // Sorting
  sortField = 'created_at';
  sortDirection = 'desc';
  
  // Table columns
  displayedColumns: string[] = ['name', 'project_name', 'status', 'created_at', 'actions'];
  
  // Project list for filtering
  projects: { id: string, name: string }[] = [];

  constructor(
    private elnService: ElnService,
    private route: ActivatedRoute,
    private snackBar: MatSnackBar
  ) { }

  ngOnInit(): void {
    this.route.queryParams.subscribe(params => {
      if (params['projectId']) {
        this.projectFilter = params['projectId'];
      }
      
      this.loadExperiments();
      this.loadProjects();
    });
  }

  loadExperiments(): void {
    this.loading = true;
    
    // If project filter is set to a specific project, use getExperiments with project ID
    if (this.projectFilter !== 'all') {
      this.elnService.getExperiments(this.projectFilter).subscribe({
        next: (response) => {
          if (response.success && response.experiments) {
            this.experiments = response.experiments;
            this.applyFilters();
          } else {
            this.error = 'Failed to load experiments';
          }
          this.loading = false;
        },
        error: (err: any) => {
          this.error = err.message || 'Failed to load experiments';
          this.loading = false;
        }
      });
    } else {
      // Otherwise, get all experiments
      this.elnService.getExperiments().subscribe({
        next: (response: any) => {
          if (response.success && response.experiments) {
            this.experiments = response.experiments;
            this.applyFilters();
          } else {
            this.error = 'Failed to load experiments';
          }
          this.loading = false;
        },
        error: (err: any) => {
          this.error = err.message || 'Failed to load experiments';
          this.loading = false;
        }
      });
    }
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

  applyFilters(): void {
    this.filteredExperiments = this.experiments.filter(experiment => {
      // Apply status filter
      if (this.statusFilter !== 'all' && experiment.status.toLowerCase() !== this.statusFilter.toLowerCase()) {
        return false;
      }
      
      // Apply search query filter
      if (this.searchQuery && !this.matchesSearchQuery(experiment)) {
        return false;
      }
      
      return true;
    });
    
    // Apply sorting
    this.sortData({
      active: this.sortField,
      direction: this.sortDirection
    } as Sort);
    
    // Update pagination
    this.totalExperiments = this.filteredExperiments.length;
    this.updateDisplayedExperiments();
  }

  matchesSearchQuery(experiment: Experiment): boolean {
    const query = this.searchQuery.toLowerCase();
    return Boolean(
      experiment.name.toLowerCase().includes(query) ||
      experiment.description.toLowerCase().includes(query) ||
      (experiment.project_id && experiment.project_id.toLowerCase().includes(query))
    );
  }

  onStatusFilterChange(): void {
    this.pageIndex = 0;
    this.applyFilters();
  }

  onProjectFilterChange(): void {
    this.pageIndex = 0;
    this.loadExperiments();
  }

  onSearchQueryChange(): void {
    this.pageIndex = 0;
    this.applyFilters();
  }

  onPageChange(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.updateDisplayedExperiments();
  }

  sortData(sort: Sort): void {
    this.sortField = sort.active;
    this.sortDirection = sort.direction;
    
    if (!sort.active || sort.direction === '') {
      this.sortField = 'created_at';
      this.sortDirection = 'desc';
    }
    
    this.filteredExperiments = this.filteredExperiments.sort((a, b) => {
      const isAsc = this.sortDirection === 'asc';
      switch (this.sortField) {
        case 'name': return this.compare(a.name, b.name, isAsc);
        case 'project': return this.compare(a.project_id || '', b.project_id || '', isAsc);
        case 'status': return this.compare(a.status, b.status, isAsc);
        case 'created_at': return this.compare(new Date(a.created_at), new Date(b.created_at), isAsc);
        default: return 0;
      }
    });
    
    this.updateDisplayedExperiments();
  }

  compare(a: any, b: any, isAsc: boolean): number {
    return (a < b ? -1 : 1) * (isAsc ? 1 : -1);
  }

  updateDisplayedExperiments(): void {
    const startIndex = this.pageIndex * this.pageSize;
    this.displayedExperiments = this.filteredExperiments.slice(startIndex, startIndex + this.pageSize);
  }

  deleteExperiment(event: Event, experimentId: string): void {
    event.stopPropagation();
    
    if (confirm('Are you sure you want to delete this experiment? This action cannot be undone.')) {
      this.elnService.deleteExperiment(experimentId).subscribe({
        next: (response) => {
          if (response.success) {
            this.experiments = this.experiments.filter(e => e.id !== experimentId);
            this.applyFilters();
            this.snackBar.open('Experiment deleted successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to delete experiment', 'Close', {
              duration: 5000
            });
          }
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to delete experiment', 'Close', {
            duration: 5000
          });
        }
      });
    }
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
}
