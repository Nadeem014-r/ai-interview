export const getStoredToken = (): string | null => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("token");
  }
  return null;
};

export const setStoredToken = (token: string) => {
  if (typeof window !== "undefined") {
    localStorage.setItem("token", token);
  }
};

export const isAuthenticated = (): boolean => {
  return !!getStoredToken();
};

export const requireAuth = (router: any): boolean => {
  if (typeof window !== "undefined") {
    const token = getStoredToken();
    if (!token) {
      router.push("/login");
      return false;
    }
    return true;
  }
  return false;
};

export const removeStoredToken = () => {
  if (typeof window !== "undefined") {
    localStorage.removeItem("token");
  }
};

