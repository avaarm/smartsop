import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ElnService, Protocol } from '../../../../services/eln-service.service';
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
import { MatChipsModule } from '@angular/material/chips';

@Component({
  selector: 'app-protocol-list',
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
    MatChipsModule
  ],
  providers: [MatSnackBar],
  templateUrl: './protocol-list.component.html',
  styleUrls: ['./protocol-list.component.scss']
})
export class ProtocolListComponent implements OnInit {
  protocols: Protocol[] = [];
  filteredProtocols: Protocol[] = [];
  displayedProtocols: Protocol[] = [];
  loading = true;
  error = '';
  
  // Filter options
  categoryFilter = 'all';
  searchQuery = '';
  
  // Pagination
  pageSize = 10;
  pageSizeOptions = [5, 10, 25, 50];
  pageIndex = 0;
  totalProtocols = 0;
  
  // Project list for filtering
  projects: { id: string, name: string }[] = [];
  selectedProjectId = 'all';
  
  // Categories
  categories: string[] = [];

  constructor(
    private elnService: ElnService,
    private snackBar: MatSnackBar
  ) { }

  ngOnInit(): void {
    this.loadProtocols();
    this.loadProjects();
  }

  loadProtocols(): void {
    this.loading = true;
    
    // Get all protocols and filter by project ID in the component if needed
    this.elnService.getProtocols().subscribe({
      next: (response) => {
        if (response.success && response.protocols) {
          // If project filter is set, filter protocols by project ID
          if (this.selectedProjectId !== 'all') {
            this.protocols = response.protocols.filter(protocol => 
              protocol.project_id === this.selectedProjectId
            );
          } else {
            this.protocols = response.protocols;
          }
          this.extractCategories();
          this.applyFilters();
        } else {
          this.error = 'Failed to load protocols';
        }
        this.loading = false;
      },
      error: (err) => {
        this.error = err.message || 'Failed to load protocols';
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

  extractCategories(): void {
    // Extract unique categories from protocols
    const categorySet = new Set<string>();
    this.protocols.forEach(protocol => {
      if (protocol.category) {
        categorySet.add(protocol.category);
      }
    });
    this.categories = Array.from(categorySet);
  }

  applyFilters(): void {
    this.filteredProtocols = this.protocols.filter(protocol => {
      // Apply category filter
      if (this.categoryFilter !== 'all' && protocol.category !== this.categoryFilter) {
        return false;
      }
      
      // Apply search query filter
      if (this.searchQuery && !this.matchesSearchQuery(protocol)) {
        return false;
      }
      
      return true;
    });
    
    // Update pagination
    this.totalProtocols = this.filteredProtocols.length;
    this.updateDisplayedProtocols();
  }

  matchesSearchQuery(protocol: Protocol): boolean {
    const query = this.searchQuery.toLowerCase();
    return Boolean(
      protocol.name.toLowerCase().includes(query) ||
      protocol.description.toLowerCase().includes(query) ||
      (protocol.category && protocol.category.toLowerCase().includes(query))
    );
  }

  onCategoryFilterChange(): void {
    this.pageIndex = 0;
    this.applyFilters();
  }

  onProjectFilterChange(): void {
    this.pageIndex = 0;
    this.loadProtocols();
  }

  onSearchQueryChange(): void {
    this.pageIndex = 0;
    this.applyFilters();
  }

  onPageChange(event: PageEvent): void {
    this.pageIndex = event.pageIndex;
    this.pageSize = event.pageSize;
    this.updateDisplayedProtocols();
  }

  updateDisplayedProtocols(): void {
    const startIndex = this.pageIndex * this.pageSize;
    this.displayedProtocols = this.filteredProtocols.slice(startIndex, startIndex + this.pageSize);
  }

  deleteProtocol(event: Event, protocolId: string): void {
    event.stopPropagation();
    
    if (confirm('Are you sure you want to delete this protocol? This action cannot be undone.')) {
      this.elnService.deleteProtocol(protocolId).subscribe({
        next: (response) => {
          if (response.success) {
            this.protocols = this.protocols.filter(p => p.id !== protocolId);
            this.applyFilters();
            this.snackBar.open('Protocol deleted successfully', 'Close', {
              duration: 3000
            });
          } else {
            this.snackBar.open(response.error || 'Failed to delete protocol', 'Close', {
              duration: 5000
            });
          }
        },
        error: (err) => {
          this.snackBar.open(err.message || 'Failed to delete protocol', 'Close', {
            duration: 5000
          });
        }
      });
    }
  }

  getVersionLabel(version: string | number): string {
    return `v${version}`;
  }
}
