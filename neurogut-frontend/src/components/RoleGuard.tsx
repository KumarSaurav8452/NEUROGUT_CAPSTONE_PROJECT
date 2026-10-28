"use client";
import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

type Role = "admin" | "clinician" | "researcher";

interface RoleGuardProps {
  allowedRoles: Role[];
  children: React.ReactNode;
}

/**
 * RoleGuard — wraps page content and redirects to /unauthorized
 * if the current user's role is not in allowedRoles.
 *
 * Usage:
 *   <RoleGuard allowedRoles={["admin", "clinician"]}>
 *     <PageContent />
 *   </RoleGuard>
 */
export function RoleGuard({ allowedRoles, children }: RoleGuardProps) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && user && !allowedRoles.includes(user.role as Role)) {
      router.replace("/unauthorized");
    }
  }, [user, loading, allowedRoles, router]);

  if (loading) {
    return (
      <div style={{ minHeight: "60vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div className="spinner" />
      </div>
    );
  }

  if (!user || !allowedRoles.includes(user.role as Role)) {
    return null; // Redirect will fire, nothing to render
  }

  return <>{children}</>;
}
