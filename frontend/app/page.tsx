import Chat from "@/components/Chat";

export default function Home() {
  return (
    <main>
      <header>
        <h1>Mộc An Home · Trợ lý back-office</h1>
        <p className="muted">Mốc 1: agent tra cứu chính sách (RAG tiếng Việt, có trích dẫn nguồn)</p>
      </header>
      <Chat />
    </main>
  );
}
