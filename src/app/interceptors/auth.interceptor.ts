import { HttpInterceptorFn, HttpErrorResponse } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { AuthService } from '../services/auth.service';

/**
 * Attaches the JWT to API requests and, on an expired/invalid session (401),
 * clears local auth state and bounces the user to the login page.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const token = auth.token;
  const isApi = req.url.startsWith('/api');
  const authReq = token && isApi
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  // Login/register legitimately return 401 on bad credentials — let the form
  // surface that without forcing a redirect.
  const isAuthEndpoint = req.url.includes('/api/auth/login') || req.url.includes('/api/auth/register');

  return next(authReq).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && !isAuthEndpoint) {
        auth.clearSession();
        router.navigate(['/login']);
      }
      return throwError(() => err);
    })
  );
};
