import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Observable, timeout, catchError, throwError, retry } from 'rxjs';

// Project interfaces
export interface Project {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  start_date?: string;
  end_date?: string;
  team_members?: TeamMember[];
}

export interface TeamMember {
  user_id: string;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
}

export interface ProjectResponse {
  success: boolean;
  project?: Project;
  projects?: Project[];
  error?: string;
}

// Experiment interfaces
export interface Experiment {
  id: string;
  project_id: string;
  name: string;
  description: string;
  hypothesis?: string;
  status: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  start_date?: string;
  end_date?: string;
  tasks?: Task[];
  protocols?: ProtocolAssignment[];
  data?: ExperimentData[];
}

export interface Task {
  id: string;
  experiment_id: string;
  name: string;
  description: string;
  status: string;
  assigned_to?: string;
  due_date?: string;
}

export interface ExperimentData {
  id: string;
  experiment_id: string;
  data_type: string;
  name: string;
  value: any;
  created_at: string;
  created_by: string;
}

export interface ExperimentResponse {
  success: boolean;
  experiment?: Experiment;
  experiments?: Experiment[];
  error?: string;
}

// Protocol interfaces
export interface Protocol {
  id: string;
  name: string;
  description: string;
  version: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  is_published: boolean;
  steps?: ProtocolStep[];
  // Additional properties used in components
  project_id?: string;
  category?: string;
  materials?: string;
  equipment?: string;
  safety_notes?: string;
  references?: string;
}

export interface ProtocolStep {
  id: string;
  protocol_id: string;
  step_number: number;
  name: string;
  description: string;
  expected_result?: string;
  duration_minutes?: number;
  parameters?: any;
}

export interface ProtocolAssignment {
  id: string;
  protocol_id: string;
  experiment_id: string;
  status: string;
  assigned_at: string;
  assigned_by: string;
  protocol?: Protocol;
}

export interface ProtocolResponse {
  success: boolean;
  protocol?: Protocol;
  protocols?: Protocol[];
  assignments?: ProtocolAssignment[];
  error?: string;
}

// Inventory interfaces
export interface InventoryItem {
  id: string;
  name: string;
  description: string;
  category: string;
  location: string;
  quantity: number;
  unit: string;
  min_quantity?: number;
  expiration_date?: string;
  purchase_date?: string;
  catalog_number?: string;
  supplier?: string;
  price?: number;
  storage_conditions?: string;
  safety_notes?: string;
  attachments?: string;
  created_at: string;
  updated_at: string;
  created_by: string;
  status?: string;
  alerts?: InventoryAlert[];
  transactions?: InventoryTransaction[];
}

export interface InventoryTransaction {
  id: string;
  inventory_id: string;
  transaction_type: string;
  quantity: number;
  transaction_date: string;
  performed_by: string;
  notes?: string;
  experiment_id?: string;
}

export interface InventoryAlert {
  id: string;
  inventory_id: string;
  alert_type: string;
  message: string;
  created_at: string;
  resolved: boolean;
  resolved_at?: string;
  resolved_by?: string;
}

export interface InventoryResponse {
  success: boolean;
  item?: InventoryItem;
  items?: InventoryItem[];
  transaction?: InventoryTransaction;
  transactions?: InventoryTransaction[];
  alert?: InventoryAlert;
  alerts?: InventoryAlert[];
  error?: string;
}

// User interfaces
export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  department?: string;
  title?: string;
  phone?: string;
  status: string;
  created_at: string;
  last_login?: string;
  projects?: Project[];
}

export interface UserResponse {
  success: boolean;
  user?: User;
  users?: User[];
  error?: string;
}

export interface AuthResponse {
  success: boolean;
  user?: User;
  message?: string;
  error?: string;
}

@Injectable({
  providedIn: 'root'
})
export class ElnService {
  private apiUrl = 'http://localhost:5001';

  constructor(private http: HttpClient) { }

  // Timeout after 60 seconds
  private requestTimeout = 60000;
  
  // Handle HTTP errors
  private handleError(error: HttpErrorResponse | Error) {
    if (error.name === 'TimeoutError') {
      return throwError(() => new Error('Request timed out. The server is taking too long to respond.'));
    }
    
    if (error instanceof HttpErrorResponse) {
      if (error.status === 0) {
        // A client-side or network error occurred
        return throwError(() => new Error('Unable to connect to the server. Please check your connection and make sure the server is running.'));
      } else {
        // The backend returned an unsuccessful response code
        const message = error.error instanceof Object ? error.error.error || 'Server error' : 'Server error';
        return throwError(() => new Error(`Server error: ${message}`));
      }
    }
    
    // For any other type of error
    return throwError(() => error);
  }

  // Project API methods
  getProjects(filters?: { user_id?: string, status?: string }): Observable<ProjectResponse> {
    let params = new HttpParams();
    if (filters?.user_id) {
      params = params.set('user_id', filters.user_id);
    }
    if (filters?.status) {
      params = params.set('status', filters.status);
    }

    return this.http.get<ProjectResponse>(`${this.apiUrl}/api/projects`, {
      params,
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getProject(projectId: string): Observable<ProjectResponse> {
    return this.http.get<ProjectResponse>(`${this.apiUrl}/api/projects/${projectId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  createProject(project: Partial<Project>): Observable<ProjectResponse> {
    return this.http.post<ProjectResponse>(`${this.apiUrl}/api/projects`, project, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateProject(projectId: string, project: Partial<Project>): Observable<ProjectResponse> {
    return this.http.put<ProjectResponse>(`${this.apiUrl}/api/projects/${projectId}`, project, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  deleteProject(projectId: string): Observable<ProjectResponse> {
    return this.http.delete<ProjectResponse>(`${this.apiUrl}/api/projects/${projectId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Project team members
  getProjectTeamMembers(projectId: string): Observable<ProjectResponse> {
    return this.http.get<ProjectResponse>(`${this.apiUrl}/api/projects/${projectId}/team`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  addProjectTeamMember(projectId: string, userId: string, role: string): Observable<ProjectResponse> {
    return this.http.post<ProjectResponse>(`${this.apiUrl}/api/projects/${projectId}/team`, {
      user_id: userId,
      role: role
    }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  removeProjectTeamMember(projectId: string, userId: string): Observable<ProjectResponse> {
    return this.http.delete<ProjectResponse>(`${this.apiUrl}/api/projects/${projectId}/team/${userId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Experiment API methods
  getExperiments(projectId?: string, status?: string): Observable<ExperimentResponse> {
    let params = new HttpParams();
    if (projectId) {
      params = params.set('project_id', projectId);
    }
    if (status) {
      params = params.set('status', status);
    }

    return this.http.get<ExperimentResponse>(`${this.apiUrl}/api/experiments`, {
      params,
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getExperiment(experimentId: string): Observable<ExperimentResponse> {
    return this.http.get<ExperimentResponse>(`${this.apiUrl}/api/experiments/${experimentId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  createExperiment(experiment: Partial<Experiment>): Observable<ExperimentResponse> {
    return this.http.post<ExperimentResponse>(`${this.apiUrl}/api/experiments`, experiment, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateExperiment(experimentId: string, experiment: Partial<Experiment>): Observable<ExperimentResponse> {
    return this.http.put<ExperimentResponse>(`${this.apiUrl}/api/experiments/${experimentId}`, experiment, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  deleteExperiment(experimentId: string): Observable<ExperimentResponse> {
    return this.http.delete<ExperimentResponse>(`${this.apiUrl}/api/experiments/${experimentId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Experiment data
  addExperimentData(experimentId: string, data: Partial<ExperimentData>): Observable<ExperimentResponse> {
    return this.http.post<ExperimentResponse>(`${this.apiUrl}/api/experiments/${experimentId}/data`, data, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getExperimentData(experimentId: string): Observable<ExperimentResponse> {
    return this.http.get<ExperimentResponse>(`${this.apiUrl}/api/experiments/${experimentId}/data`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Protocol API methods
  getProtocols(): Observable<ProtocolResponse> {
    return this.http.get<ProtocolResponse>(`${this.apiUrl}/api/protocols`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getProtocol(protocolId: string): Observable<ProtocolResponse> {
    return this.http.get<ProtocolResponse>(`${this.apiUrl}/api/protocols/${protocolId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  createProtocol(protocol: Partial<Protocol>): Observable<ProtocolResponse> {
    return this.http.post<ProtocolResponse>(`${this.apiUrl}/api/protocols`, protocol, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateProtocol(protocolId: string, protocol: Partial<Protocol>): Observable<ProtocolResponse> {
    return this.http.put<ProtocolResponse>(`${this.apiUrl}/api/protocols/${protocolId}`, protocol, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  deleteProtocol(protocolId: string): Observable<ProtocolResponse> {
    return this.http.delete<ProtocolResponse>(`${this.apiUrl}/api/protocols/${protocolId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Protocol steps
  createProtocolStep(protocolId: string, step: Partial<ProtocolStep>): Observable<ProtocolResponse> {
    return this.http.post<ProtocolResponse>(`${this.apiUrl}/api/protocols/${protocolId}/steps`, step, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateProtocolStep(protocolId: string, stepId: string, step: Partial<ProtocolStep>): Observable<ProtocolResponse> {
    return this.http.put<ProtocolResponse>(`${this.apiUrl}/api/protocols/${protocolId}/steps/${stepId}`, step, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  deleteProtocolStep(protocolId: string, stepId: string): Observable<ProtocolResponse> {
    return this.http.delete<ProtocolResponse>(`${this.apiUrl}/api/protocols/${protocolId}/steps/${stepId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Protocol assignments
  assignProtocol(experimentId: string, protocolId: string): Observable<ProtocolResponse> {
    return this.http.post<ProtocolResponse>(`${this.apiUrl}/api/experiments/${experimentId}/protocols`, {
      protocol_id: protocolId
    }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getProtocolAssignments(experimentId: string): Observable<ProtocolResponse> {
    return this.http.get<ProtocolResponse>(`${this.apiUrl}/api/experiments/${experimentId}/protocols`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateProtocolAssignment(experimentId: string, assignmentId: string, status: string): Observable<ProtocolResponse> {
    return this.http.put<ProtocolResponse>(`${this.apiUrl}/api/experiments/${experimentId}/protocols/${assignmentId}`, {
      status: status
    }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Inventory API methods
  getInventoryItems(filters?: { category?: string, low_stock?: boolean, expiring_soon?: boolean }): Observable<InventoryResponse> {
    let params = new HttpParams();
    if (filters?.category) {
      params = params.set('category', filters.category);
    }
    if (filters?.low_stock !== undefined) {
      params = params.set('low_stock', filters.low_stock.toString());
    }
    if (filters?.expiring_soon !== undefined) {
      params = params.set('expiring_soon', filters.expiring_soon.toString());
    }

    return this.http.get<InventoryResponse>(`${this.apiUrl}/api/inventory`, {
      params,
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getInventoryItem(itemId: string): Observable<InventoryResponse> {
    return this.http.get<InventoryResponse>(`${this.apiUrl}/api/inventory/${itemId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  createInventoryItem(item: Partial<InventoryItem>): Observable<InventoryResponse> {
    return this.http.post<InventoryResponse>(`${this.apiUrl}/api/inventory`, item, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateInventoryItem(itemId: string, item: Partial<InventoryItem>): Observable<InventoryResponse> {
    return this.http.put<InventoryResponse>(`${this.apiUrl}/api/inventory/${itemId}`, item, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  deleteInventoryItem(itemId: string): Observable<InventoryResponse> {
    return this.http.delete<InventoryResponse>(`${this.apiUrl}/api/inventory/${itemId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateInventoryItemQuantity(itemId: string, quantity: number): Observable<InventoryResponse> {
    return this.http.put<InventoryResponse>(`${this.apiUrl}/api/inventory/${itemId}/quantity`, { quantity }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getInventoryItemUsageHistory(itemId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/api/inventory/${itemId}/usage`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getInventoryCategories(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/api/inventory/categories`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getInventoryLocations(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/api/inventory/locations`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Inventory transactions
  createInventoryTransaction(itemId: string, transaction: Partial<InventoryTransaction>): Observable<InventoryResponse> {
    return this.http.post<InventoryResponse>(`${this.apiUrl}/api/inventory/${itemId}/transactions`, transaction, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getInventoryTransactions(itemId: string): Observable<InventoryResponse> {
    return this.http.get<InventoryResponse>(`${this.apiUrl}/api/inventory/${itemId}/transactions`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Inventory alerts
  getInventoryAlerts(resolved?: boolean): Observable<InventoryResponse> {
    let params = new HttpParams();
    if (resolved !== undefined) {
      params = params.set('resolved', resolved.toString());
    }

    return this.http.get<InventoryResponse>(`${this.apiUrl}/api/inventory/alerts`, {
      params,
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  resolveInventoryAlert(alertId: string): Observable<InventoryResponse> {
    return this.http.put<InventoryResponse>(`${this.apiUrl}/api/inventory/alerts/${alertId}/resolve`, {}, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // User API methods
  getUsers(role?: string, status?: string): Observable<UserResponse> {
    let params = new HttpParams();
    if (role) {
      params = params.set('role', role);
    }
    if (status) {
      params = params.set('status', status);
    }

    return this.http.get<UserResponse>(`${this.apiUrl}/api/users`, {
      params,
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getUser(userId: string): Observable<UserResponse> {
    return this.http.get<UserResponse>(`${this.apiUrl}/api/users/${userId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  createUser(user: Partial<User> & { password: string }): Observable<UserResponse> {
    return this.http.post<UserResponse>(`${this.apiUrl}/api/users`, user, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateUser(userId: string, user: Partial<User>): Observable<UserResponse> {
    return this.http.put<UserResponse>(`${this.apiUrl}/api/users/${userId}`, user, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  updateUserStatus(userId: string, status: string): Observable<UserResponse> {
    return this.http.put<UserResponse>(`${this.apiUrl}/api/users/${userId}/status`, { status }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  deleteUser(userId: string): Observable<UserResponse> {
    return this.http.delete<UserResponse>(`${this.apiUrl}/api/users/${userId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getCurrentUser(): Observable<UserResponse> {
    return this.http.get<UserResponse>(`${this.apiUrl}/api/users/current`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  getUserActivity(userId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/api/users/${userId}/activity`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  assignUserToProject(userId: string, projectId: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/api/users/${userId}/projects`, { project_id: projectId }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  removeUserFromProject(userId: string, projectId: string): Observable<any> {
    return this.http.delete<any>(`${this.apiUrl}/api/users/${userId}/projects/${projectId}`, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  // Authentication
  login(username: string, password: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/api/auth/login`, {
      username,
      password
    }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }

  logout(userId: string): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/api/auth/logout`, {
      user_id: userId
    }, {
      withCredentials: true
    }).pipe(
      retry(1),
      timeout(this.requestTimeout),
      catchError(error => this.handleError(error))
    );
  }
}
