import React, { Component} from "react";
import styles from "./Dashboard.module.css";


const Dashboard = () => {
  return (
    <>  
    <div className="h-250 w-full flex items-center justify-center bg-lime-50">
      <div className="grid h-full w-full  grid-cols-3 auto-rows-auto gap-2 p-5 ">
         <div className='col-span-1 row-span-1 rounded-xl bg-gray-400 text-center'>sect 1</div>
         <div className='col-span-1 row-span-1 rounded-xl bg-gray-400 text-center'>sect 2</div>
         <div className='col-span-1 row-span-1 rounded-xl bg-gray-400 text-center'>sect 3</div>
         <div className='col-span-1 row-span-1 rounded-xl bg-gray-400 text-center'>sect 4</div> 
         <div className='col-span-1 row-span-1 rounded-xl bg-gray-400 text-center'>sect 5</div>
         <div className='col-span-1 row-span-1 rounded-xl bg-gray-400 text-center'>sect 6</div> 
         <div className='col-span-2 row-span-1 rounded-xl bg-gray-400 text-center'>sect 7</div> 
        <p>loaddash</p>
        </div>
    </div>
    <p>help help</p>
    </>
  );
};

export default Dashboard;