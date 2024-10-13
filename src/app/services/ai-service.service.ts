import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class AIService {
  constructor(private http: HttpClient) { }

  // This method will call the flask API to generate the SOP
  generateSOP(data: any): Observable<any> {
    return this.http.post('/api/generate_sop', data);
  }
}
