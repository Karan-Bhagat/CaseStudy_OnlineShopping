#Importing SQL
import sqlite3

#Making Connecting
conn = sqlite3.connect('DB1')

#Creating Cursor 
c = conn.cursor()

#Function to Extract data from file
def Execute(file_name):
    #Opening File
    file = open(file_name)

    #Reading File
    data = file.read()

    #Splitting a Whole String into Different Rows
    data = data.split('\n')

    #Removing blank Row
    data.remove('')
    
    return data

#Function to Convert Raw Data Into Usable Form
def Usable(data):
    lst = []
    for i in data:
        dctnry = {}
        dctnry.update({'Transaction_Id' : i[0:6]})
        dctnry.update({'Customer_Id' : i[6:12]})
        dctnry.update({'Customer_Name' : i[12:32]})
        dctnry.update({'Customer_Addr_Id' : i[32:37]})
        dctnry.update({'Product_Id' : i[37:44]})
        dctnry.update({'Product_Nm' : i[44:74]})
        dctnry.update({'ProductPrice' : i[74:80]})
        dctnry.update({'ProductQuantity' : i[80:84]})
        dctnry.update({'Status' : i[84:96]})
        dctnry.update({'Transaction_time_stamp' : i[96:116]})
        dctnry.update({'Ordered_Date' : i[116:127]})
        dctnry.update({'Shipment_Date' : i[127:138]})
        dctnry.update({'Delivered_Date' : i[138:149]})
        lst.append(dctnry)
        
    return lst

#Function to Print Table
def Print():
    c.execute("SELECT * FROM 'Transaction'")
    myresult = c.fetchall()
    for x in myresult:
        print(x)

#Function to get Final Data from 'Transection' Table
def Final_data():
    c.execute("SELECT * FROM 'Transaction'")
    myresult = c.fetchall()

    #Creating List of Columns names Malually
    column_list = ['Sequence' ,'Transaction_Id', 'Customer_Id', 'Customer_Name', 'Customer_Addr_Id', 'Product_Id', 'Product_Nm', 'ProductPrice', 'ProductQuantity', 'Status', 'Transaction_time_stamp', 'Ordered_Date', 'Shipment_Date', 'Delivered_Date', 'ACTIVE_IND']

    #Collecting Data in Form of List of Dictionaries
    final_data = []
    for i in range ( len(myresult)):
        dictnry = {}
        for j in range (len(myresult[i])):
            dictnry.update({column_list[j] : myresult[i][j]})
        final_data.append(dictnry)
        
    return final_data

#Function to Insert Records in 'Transection Table'
def Insert(dctnry):
    dctnry.update({'ACTIVE_IND' : 'Y'})
    temp_list = []
    for i in dctnry:
        temp_list.append(dctnry[i])
    sql = "INSERT INTO 'Transaction' (Transaction_Id, Customer_Id, Customer_Name, Customer_Addr_Id, Product_Id, Product_Nm, ProductPrice, ProductQuantity, Status, Transaction_time_stamp, Ordered_Date, Shipment_Date, Delivered_Date, ACTIVE_IND) VALUES " + str(tuple(temp_list))
    c.execute(sql)

#Function for the Main Logic
def Main_logic( lst, final_data):
    for dctnry in lst:
        flag = 0
        for j in final_data:
            if j['Transaction_Id'] == dctnry['Transaction_Id'] and j['Customer_Id'] == dctnry['Customer_Id'] and j['Product_Id'] == dctnry['Product_Id']:
                flag = 1
                sql = "UPDATE 'Transaction' SET ACTIVE_IND = 'N' WHERE Transaction_Id = " + str(j['Transaction_Id']) + " and Customer_Id = " + str(j['Customer_Id']) + " and Product_Id = " + str(j['Product_Id'])
                c.execute(sql)
                conn.commit()
                Insert(dctnry)
                break
        if flag == 0:
            Insert(dctnry)
    conn.commit()

#Function to Track the Customer Data
def processOnlineshopping(file_name):
    data = Execute(file_name)
    lst = Usable(data)
    
    if file_name == 'Day1.txt':
        # Inserting Values of Day 1 in Table
        for dctnry in lst:
            Insert(dctnry)
        conn.commit()
    else:
        final_data = Final_data()
        Main_logic(lst, final_data)
        
    return Print()

def main():
    #Drop Table If Needed
    sql = " DROP TABLE IF EXISTS 'Transaction'"
    c.execute(sql)

    #Creating Table
    c.execute("CREATE TABLE 'Transaction' (Sequence INTEGER PRIMARY KEY, Transaction_Id VARCHAR(6), Customer_Id VARCHAR(6), Customer_Name VARCHAR(20), Customer_Addr_Id VARCHAR(5), Product_Id VARCHAR(7), Product_Nm VARCHAR(30), ProductPrice VARCHAR(6), ProductQuantity VARCHAR(4), Status VARCHAR(12), Transaction_time_stamp VARCHAR(20), Ordered_Date VARCHAR(11), Shipment_Date VARCHAR(11), Delivered_Date VARCHAR(11), ACTIVE_IND VARCHAR(1))")

    #Day 1
    print('----------------------------------------------------------------------------------------------')
    print('Day 1')
    print('----------------------------------------------------------------------------------------------')
    processOnlineshopping('Day1.txt')
    print()
    print()

    #Day 2
    print('----------------------------------------------------------------------------------------------')
    print('Day 2')
    print('----------------------------------------------------------------------------------------------')
    processOnlineshopping('Day2.txt')
    print()
    print()

    #Day 3
    print('----------------------------------------------------------------------------------------------')
    print('Day 3')
    print('----------------------------------------------------------------------------------------------')
    processOnlineshopping('Day3.txt')
    print()
    print()

if __name__ == '__main__':
    main()
