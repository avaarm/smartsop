import { Component, OnInit, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ElnService, Project } from '../../../../services/eln-service.service';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';

@Component({
  selector: 'app-project-list',
  standalone: true,
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
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
    MatSnackBarModule
  ],
  providers: [MatSnackBar],
  templateUrl: './project-list.component.html',
  styleUrls: ['./project-list.component.scss']
})
export class ProjectListComponent implements OnInit {
  projects: Project[] = [];
  filteredProjects: Project[] = [];
  loading = true;
  error = '';
  
  // Filter options
  statusFilter = 'all';
  searchQuery = '';
  
  constructor(
    private elnService: ElnService,
    private snackBar: MatSnackBar
  ) { }

  ngOnInit(): void {
    this.loadProjects();
  }

  loadProjects(): void {
    this.loading = true;
    this.elnService.getProjects().subscribe({
      next: (response) => {
        if (response.success && response.projects) {
          this.projects = response.projects;
          this.applyFilters();
        } else {
          this.error = 'Failed to load projects';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load projects';
        this.loading = false;
      }
    });
  }

  applyFilters(): void {
    this.filteredProjects = this.projects.filter(project => {
      // Apply status filter
      if (this.statusFilter !== 'all' && project.status.toLowerCase() !== this.statusFilter.toLowerCase()) {
        return false;
      }
      
      // Apply search query filter
      if (this.searchQuery && !this.matchesSearchQuery(project)) {
        return false;
      }
      
      return true;
    });
  }

  matchesSearchQuery(project: Project): boolean {
    const query = this.searchQuery.toLowerCase();
    return (
      project.name.toLowerCase().includes(query) ||
      project.description.toLowerCase().includes(query)
    );
  }

  onStatusFilterChange(): void {
    this.applyFilters();
  }

  onSearchQueryChange(): void {
    this.applyFilters();
  }

  deleteProject(event: Event, projectId: string): void {
    event.stopPropagation();
    
    if (confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
      this.elnService.deleteProject(projectId).subscribe({
        next: (response) => {
          if (response.success) {
            this.projects = this.projects.filter(p => p.id !== projectId);
            this.applyFilters();
            this.snackBar.open('Project deleted successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to delete project', 'Close', {
              duration: 5000
            });
          }
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to delete project', 'Close', {
            duration: 5000
          });
        }
      });
    }
  }

  getProjectStatusClass(status: string): string {
    switch (status.toLowerCase()) {
      case 'active':
        return 'status-active';
      case 'completed':
        return 'status-completed';
      case 'on hold':
        return 'status-on-hold';
      default:
        return 'status-default';
    }
  }
}
