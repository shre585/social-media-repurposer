import { Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Home from "./pages/Home.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Results from "./pages/Results.jsx";

export default function App() {
  return (
    <>
      <Navbar />
      <main className="container">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/results/:jobId" element={<Results />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>
      <footer className="footer">Made for creators who'd rather create than edit. ✨</footer>
    </>
  );
}
