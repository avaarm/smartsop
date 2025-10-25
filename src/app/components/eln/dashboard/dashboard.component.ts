import { Component, OnInit, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { RouterModule } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { ElnService, Project, Experiment, InventoryAlert } from '../../../services/eln-service.service';

// Angular Material imports
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTableModule, MatCellDef, MatHeaderCellDef, MatColumnDef, MatHeaderRowDef, MatRowDef } from '@angular/material/table';
import { MatTableDataSource } from '@angular/material/table';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatSortModule } from '@angular/material/sort';
import { MatBadgeModule } from '@angular/material/badge';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  imports: [
    CommonModule,
    RouterModule,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatTabsModule,
    MatTableModule,
    MatBadgeModule,
    MatProgressSpinnerModule,
    MatSortModule,
    MatDividerModule,
    MatTooltipModule,
    MatMenuModule,
    MatPaginatorModule,
    MatCellDef,
    MatHeaderCellDef,
    MatColumnDef,
    MatHeaderRowDef,
    MatRowDef
  ],
  providers: [DatePipe],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.scss']
})
export class DashboardComponent implements OnInit {
  projects: Project[] = [];
  recentExperiments: Experiment[] = [];
  inventoryAlerts: InventoryAlert[] = [];
  loading = {
    projects: true,
    experiments: true,
    alerts: true
  };
  error = {
    projects: '',
    experiments: '',
    alerts: ''
  };

  constructor(private elnService: ElnService) { }

  ngOnInit(): void {
    this.loadDashboardData();
  }

  loadDashboardData(): void {
    // Load projects
    this.elnService.getProjects().subscribe({
      next: (response) => {
        if (response.success && response.projects) {
          this.projects = response.projects;
        }
        this.loading.projects = false;
      },
      error: (err) => {
        this.error.projects = err.message || 'Failed to load projects';
        this.loading.projects = false;
      }
    });

    // Load recent experiments
    this.elnService.getExperiments().subscribe({
      next: (response) => {
        if (response.success && response.experiments) {
          // Sort by most recent first and limit to 5
          this.recentExperiments = response.experiments
            .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
            .slice(0, 5);
        }
        this.loading.experiments = false;
      },
      error: (err) => {
        this.error.experiments = err.message || 'Failed to load experiments';
        this.loading.experiments = false;
      }
    });

    // Load inventory alerts
    this.elnService.getInventoryAlerts(false).subscribe({
      next: (response) => {
        if (response.success && response.alerts) {
          this.inventoryAlerts = response.alerts;
        }
        this.loading.alerts = false;
      },
      error: (err) => {
        this.error.alerts = err.message || 'Failed to load inventory alerts';
        this.loading.alerts = false;
      }
    });
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

  getExperimentStatusClass(status: string): string {
    switch (status.toLowerCase()) {
      case 'in progress':
        return 'status-active';
      case 'completed':
        return 'status-completed';
      case 'planned':
        return 'status-planned';
      default:
        return 'status-default';
    }
  }

  getAlertTypeClass(type: string): string {
    switch (type.toLowerCase()) {
      case 'low_stock':
        return 'alert-warning';
      case 'expiry':
        return 'alert-danger';
      default:
        return 'alert-info';
    }
  }

  resolveAlert(alertId: string): void {
    this.elnService.resolveInventoryAlert(alertId).subscribe({
      next: (response) => {
        if (response.success) {
          // Remove the resolved alert from the list
          this.inventoryAlerts = this.inventoryAlerts.filter(alert => alert.id !== alertId);
        }
      },
      error: (err) => {
        console.error('Failed to resolve alert:', err);
      }
    });
  }

  getProjectName(projectId: string): string {
    if (!this.projects || !projectId) return 'Unknown Project';
    const project = this.projects.find(p => p.id === projectId);
    return project ? project.name : 'Unknown Project';
  }
}
