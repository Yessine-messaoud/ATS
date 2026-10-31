import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Assistant replies: GitHub-flavoured Markdown (tables, lists). Raw HTML is never rendered. */
export function Markdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: (props) => <p className="my-2 first:mt-0 last:mb-0" {...props} />,
        ul: (props) => <ul className="my-2 list-disc space-y-1 pl-5" {...props} />,
        ol: (props) => <ol className="my-2 list-decimal space-y-1 pl-5" {...props} />,
        h1: (props) => <h3 className="mb-1 mt-3 font-semibold" {...props} />,
        h2: (props) => <h3 className="mb-1 mt-3 font-semibold" {...props} />,
        h3: (props) => <h3 className="mb-1 mt-3 font-semibold" {...props} />,
        a: (props) => <a className="text-brand-600 underline dark:text-brand-400" target="_blank" rel="noreferrer" {...props} />,
        code: (props) => <code className="rounded bg-zinc-100 px-1 py-0.5 font-mono text-xs dark:bg-zinc-800" {...props} />,
        pre: (props) => <pre className="my-2 overflow-x-auto rounded-lg bg-zinc-100 p-3 text-xs dark:bg-zinc-800" {...props} />,
        blockquote: (props) => <blockquote className="my-2 border-l-2 border-zinc-300 pl-3 text-zinc-600 dark:border-zinc-700 dark:text-zinc-400" {...props} />,
        table: (props) => (
          <div className="my-2 overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-700">
            <table className="w-full text-left text-xs" {...props} />
          </div>
        ),
        thead: (props) => <thead className="bg-zinc-50 dark:bg-zinc-800/60" {...props} />,
        th: (props) => <th className="px-2.5 py-1.5 font-semibold" {...props} />,
        td: (props) => <td className="border-t border-zinc-200 px-2.5 py-1.5 dark:border-zinc-700" {...props} />,
      }}
    >
      {children}
    </ReactMarkdown>
  );
}
