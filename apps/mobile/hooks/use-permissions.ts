/**
 * usePermissions — Simple 3-permission system for agent actions.
 */

import { useState, useCallback, useRef } from 'react';

export type PermissionType = 'read' | 'edit' | 'execute';

export type PermissionRequest = {
  id: string;
  type: PermissionType;
  description: string;
  detail?: string;
};

export type PermissionState = {
  read: boolean;
  edit: boolean;
  execute: boolean;
};

type PendingRequest = {
  request: PermissionRequest;
  resolve: (granted: boolean) => void;
};

export function usePermissions() {
  const [permissions, setPermissions] = useState<PermissionState>({
    read: false,
    edit: false,
    execute: false,
  });

  const [pendingRequest, setPendingRequest] = useState<PermissionRequest | null>(null);
  const pendingRef = useRef<PendingRequest | null>(null);
  const requestIdRef = useRef(0);

  const grantPermission = useCallback((type: PermissionType) => {
    setPermissions((prev) => ({ ...prev, [type]: true }));
  }, []);

  const grantAll = useCallback(() => {
    setPermissions({ read: true, edit: true, execute: true });
  }, []);

  const revokeAll = useCallback(() => {
    setPermissions({ read: false, edit: false, execute: false });
  }, []);

  const hasPermission = useCallback(
    (type: PermissionType) => permissions[type],
    [permissions]
  );

  const requestPermission = useCallback(
    async (type: PermissionType, description: string, detail?: string): Promise<boolean> => {
      if (permissions[type]) return true;

      const request: PermissionRequest = {
        id: `perm-${++requestIdRef.current}`,
        type,
        description,
        detail,
      };

      return new Promise<boolean>((resolve) => {
        pendingRef.current = { request, resolve };
        setPendingRequest(request);
      });
    },
    [permissions]
  );

  const respondToRequest = useCallback((granted: boolean, grantForSession = false) => {
    const pending = pendingRef.current;
    if (!pending) return;

    if (granted && grantForSession) {
      setPermissions((prev) => ({ ...prev, [pending.request.type]: true }));
    }

    pending.resolve(granted);
    pendingRef.current = null;
    setPendingRequest(null);
  }, []);

  return {
    permissions,
    pendingRequest,
    hasPermission,
    grantPermission,
    grantAll,
    revokeAll,
    requestPermission,
    respondToRequest,
  };
}

export type UsePermissionsReturn = ReturnType<typeof usePermissions>;
