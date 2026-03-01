/**
 * PermissionContext — Provides permission state throughout the app.
 */

import { createContext, useContext, type ReactNode } from 'react';
import { usePermissions, type UsePermissionsReturn } from '@/hooks/use-permissions';

const PermissionContext = createContext<UsePermissionsReturn | null>(null);

export function PermissionProvider({ children }: { children: ReactNode }) {
  const permissions = usePermissions();

  return (
    <PermissionContext.Provider value={permissions}>
      {children}
    </PermissionContext.Provider>
  );
}

export function usePermissionContext() {
  const context = useContext(PermissionContext);
  if (!context) {
    throw new Error('usePermissionContext must be used within PermissionProvider');
  }
  return context;
}
